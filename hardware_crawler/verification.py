import re
from typing import Dict, Any, List, Optional
from .models import Listing, CanonicalSpec, VerificationResult, ValidationStatus
from .canonicalization import PartNormalizer

class AttributeExtractor:
    """Extracts structured data from raw listing text (title + description)."""
    
    @staticmethod
    def extract_attributes(title: str, description: str) -> Dict[str, Any]:
        """
        Extracts: VRAM, Manufacturer, Model Series, Condition Tokens.
        """
        combined = (title + " " + description).upper()
        attrs = {}
        
        # VRAM Extraction (e.g., "8GB", "12 GB")
        vram_match = re.search(r'(\d+)\s*GB', combined) # simplistic but often works for headlines
        if vram_match:
            try:
                attrs['vram'] = int(vram_match.group(1))
            except:
                pass
                
        # Manufacturer
        manu = PartNormalizer.normalize_manufacturer(title) # trust title more
        if not manu:
             manu = PartNormalizer.normalize_manufacturer(description)
        if manu:
            attrs['manufacturer'] = manu
            
        # Model Tokens (Ti/Super/XT)
        # We need to know WHAT we are looking for usually, but we can extract generic flags
        if "TI" in combined.split(): attrs['is_ti'] = True
        if "SUPER" in combined: attrs['is_super'] = True
        
        # Condition signals
        if "DEFEKT" in combined: attrs['defect'] = True
        if "OVP" in combined: attrs['ovp'] = True # Original packaging
        if any(re.search(rf'\b{re.escape(x)}\b', title.upper()) for x in ["SUCHE", "GESUCH", "KAUFE", "ANKAUF", "TAUSCH", "TAUSCHE"]): 
            attrs['is_search_request'] = True
        if re.search(r'\bS:\b', title.upper()):
            attrs['is_search_request'] = True
        
        return attrs

class VerificationEngine:
    """Decides if a listing is a match for a CanonicalSpec."""
    
    @staticmethod
    def verify(listing: Listing, spec: CanonicalSpec, ai_agent=None) -> VerificationResult:
        reasons = []
        flags = []
        confidence = 1.0
        
        # 0. Extraction
        extracted_attrs = AttributeExtractor.extract_attributes(listing.title, listing.description)
        listing.raw_attributes = extracted_attrs
        
        combined_text = (listing.title + " " + listing.description).upper()
        title_upper = listing.title.upper()
        
        # check for search request/trade "SUCHE" / "TAUSCH"
        if extracted_attrs.get('is_search_request') or "SUCHE" in title_upper or "TAUSCH" in title_upper:
            return VerificationResult(
                status=ValidationStatus.REJECT,
                confidence_score=0.0,
                matched_attributes=extracted_attrs,
                rejection_reasons=["Search Request or Trade (Tausch/Suche)"]
            )
            
        # 1. Hard Rules (Must Contain)
        for token in spec.must_contain_tokens:
            if token.upper() not in combined_text:
                # Critical Fail if missing in Title? 
                # Strict Policy: Key model tokens MUST be in Title for high confidence
                if token.upper() not in title_upper:
                     reasons.append(f"Missing mandatory token '{token}' in title")
                     confidence -= 0.6
                else:
                    confidence -= 0.3 # Missing in desc but present in title is ok? Wait
                    # Logic error in Loop: if token not in combined, it's missing everywhere.
                    pass
        
        # Re-check Must Contain roughly
        missing_mandatory = [t for t in spec.must_contain_tokens if t.upper() not in combined_text]
        if missing_mandatory:
            return VerificationResult(
                status=ValidationStatus.REJECT,
                confidence_score=0.0,
                matched_attributes=extracted_attrs,
                rejection_reasons=[f"Missing mandatory tokens: {missing_mandatory}"]
            )

        # 2. Must Exclude (Negatives)
        for token in spec.must_exclude_tokens:
            if token.upper() in title_upper: # Title exclusions are stronger
                return VerificationResult(
                    status=ValidationStatus.REJECT,
                    confidence_score=0.0,
                    matched_attributes=extracted_attrs,
                    rejection_reasons=[f"Forbidden token found: {token}"]
                )
        
        # 3. Attribute Verification (e.g. VRAM)
        expected_vram = spec.expected_attributes.get('vram')
        if expected_vram and 'vram' in extracted_attrs:
            actual = extracted_attrs['vram']
            if actual not in expected_vram:
                # Mismatch! e.g. 3060 8GB vs 12GB
                reasons.append(f"VRAM Mismatch: Found {actual}GB, expected {expected_vram}GB")
                confidence -= 0.5
        
        # 4. Defect Detection
        if extracted_attrs.get('defect'):
            flags.append("Defect/Prohibitive Condition detected")
            reasons.append("Item is marked as defective")
            # If user wants working parts, this is a REJECT or distinct status.
            # Using REVIEW for now or specialized Reject? 
            # Plan says: "filter out".
            return VerificationResult(
                status=ValidationStatus.REVIEW, # Or Reject
                confidence_score=0.1,
                matched_attributes=extracted_attrs,
                rejection_reasons=["Defective"]
            )
            
        # 4b. Price Check (Filter out VB 0€ or broken prices, and 1-5€ scam listings)
        if listing.price <= 5.0:
            return VerificationResult(
                status=ValidationStatus.REJECT,
                confidence_score=0.0,
                matched_attributes=extracted_attrs,
                rejection_reasons=["Price is suspiciously low (<= 5€), likely fake VB"]
            )

        # Final Decision
        status = ValidationStatus.PASS
        if confidence < 0.7:
            status = ValidationStatus.REVIEW
        if confidence < 0.4:
            status = ValidationStatus.REJECT
            
        if reasons:
            status = ValidationStatus.REVIEW # Downgrade if any specific reasons exist
            
        # 5. AI Verification (High Precision)
        # Only check if passing so far and AI is enabled
        if status in [ValidationStatus.PASS, ValidationStatus.REVIEW] and ai_agent:
            ai_res = ai_agent.verify_listing(spec.name, listing.title, listing.description)
            if not ai_res.get("is_valid", False):
                status = ValidationStatus.REJECT # AI Overrule
                confidence = 0.0
                reasons.append(f"AI Rejection: {ai_res.get('reason')}")
            else:
                # AI confirms valid
                confidence = max(confidence, 0.9) # Boost confidence
                flags.append("AI Verified: True")

        return VerificationResult(
            status=status,
            confidence_score=max(0.0, confidence),
            matched_attributes=extracted_attrs,
            rejection_reasons=reasons,
            review_flags=flags
        )

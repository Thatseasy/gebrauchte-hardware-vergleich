import re
from typing import Dict, Any, List, Optional
from .models import Listing, CanonicalSpec, VerificationResult, ValidationStatus
from .canonicalization import PartNormalizer

class AttributeExtractor:
    """Extracts structured data from raw listing text (title + description)."""
    
    BUNDLE_KEYWORDS = [
        "KOMPLETT PC", "GAMING PC", "GAMER PC", "GAMING RECHNER", 
        "KOMPLETT-PC", "PC SYSTEM", "KOMPLETTER PC", "PC SETUP"
    ]
    
    SEARCH_TRADE_KEYWORDS = [
        "SUCHE", "GESUCH", "KAUFE", "ANKAUF", "TAUSCH", "TAUSCHE", "VERLEIH", "MIETEN"
    ]

    @classmethod
    def extract_attributes(cls, title: Optional[str], description: Optional[str]) -> Dict[str, Any]:
        """
        Extracts: VRAM, Manufacturer, Model Series, Condition Tokens, Bundle Indicators.
        """
        title_str = str(title or "")
        desc_str = str(description or "")
        combined = (title_str + " " + desc_str).upper()
        title_upper = title_str.upper()
        attrs: Dict[str, Any] = {}
        
        # 1. VRAM Extraction (Distinguish GPU VRAM from system RAM like '16 GB RAM')
        def get_vram_matches(text: str) -> List[int]:
            found = []
            for m in re.finditer(r'(\d{1,2})\s*GB\s*(?:VRAM|GDDR\d*)', text, re.IGNORECASE):
                found.append(int(m.group(1)))
            for m in re.finditer(r'(\d{1,2})\s*GB(?!\s*(?:RAM|DDR|ARBEITSSPEICHER))\b', text, re.IGNORECASE):
                val = int(m.group(1))
                if val not in found:
                    found.append(val)
            return [v for v in found if v in [4, 6, 8, 10, 11, 12, 16, 20, 24]]

        vrams = get_vram_matches(title_str)
        if not vrams:
            vrams = get_vram_matches(desc_str)
        if vrams:
            attrs['vram'] = vrams[0]
                
        # 2. Manufacturer
        manu = PartNormalizer.normalize_manufacturer(title_str)
        if not manu:
            manu = PartNormalizer.normalize_manufacturer(desc_str)
        if manu:
            attrs['manufacturer'] = manu
            
        # 3. Model Suffixes (Check for negations like 'keine Ti')
        for m in re.finditer(r'\bTI\b', title_upper):
            start = max(0, m.start() - 20)
            prefix = title_upper[start:m.start()]
            if not re.search(r'\b(KEIN|KEINE|KEINEN|NICHT)\s*$', prefix):
                attrs['is_ti'] = True
                break
        words = title_upper.split()
        if "SUPER" in words: attrs['is_super'] = True
        if "XTX" in words: attrs['is_xtx'] = True
        elif "XT" in words: attrs['is_xt'] = True
        
        # 4. Condition Signals (Defect check with negation support: 'nicht defekt', 'kein Bastler')
        defect_matches = list(re.finditer(r'\b(DEFEKT\w*|BASTLER\w*|ERSATZTEIL\w*)\b', combined, re.IGNORECASE))
        has_defect = False
        for dm in defect_matches:
            start = max(0, dm.start() - 25)
            prefix = combined[start:dm.start()]
            if re.search(r'\b(NICHT|KEIN|KEINE|KEINEN|OHNE)\s*$', prefix, re.IGNORECASE):
                continue
            has_defect = True
            break
        if has_defect:
            attrs['defect'] = True

        if "OVP" in combined or "ORIGINALVERPACKUNG" in combined:
            attrs['ovp'] = True
            
        # 5. Search / Trade Request (Negation support: 'kein Tausch', 'keine Suche')
        for kw in cls.SEARCH_TRADE_KEYWORDS:
            for match in re.finditer(rf'\b{re.escape(kw)}\b', title_upper):
                start = max(0, match.start() - 25)
                prefix = title_upper[start:match.start()]
                if re.search(r'\b(KEIN|KEINE|KEINEN|NICHT)\s*$', prefix):
                    continue
                attrs['is_search_request'] = True
                break
        if re.search(r'\bS:\b', title_upper):
            attrs['is_search_request'] = True
            
        # 6. Complete PC Bundle Indicator
        if any(x in title_upper for x in cls.BUNDLE_KEYWORDS):
            attrs['bundle_detected'] = True
            
        # 7. Box-Only / Cooler-Only Scam Warnings (Checked in both title and description)
        box_patterns = [
            r'\bNUR\s+OVP\b', r'\bLEERKARTON\b', r'\bOVP\s+LEER\b', r'\bNUR\s+KARTON\b',
            r'\bNUR\s+DIE\s+OVP\b', r'\bNUR\s+AUF\s+DIE\s+OVP\b', r'\bOHNE\s+GRAFIKKARTE\b',
            r'\bOHNE\s+GPU\b', r'\bLEERVERPACKUNG\b'
        ]
        if any(re.search(pat, combined, re.IGNORECASE) for pat in box_patterns):
            attrs['box_or_parts_only'] = True
        
        return attrs

class VerificationEngine:
    """
    Tier 1 Script-Heuristic Filter.
    Classifies listings into PASS, REVIEW, or REJECT, and generates confidence scores
    and review flags that dictate whether Tier 2 LLM active verification is required.
    """
    
    @staticmethod
    def verify(listing: Listing, spec: CanonicalSpec, ai_agent=None) -> VerificationResult:
        reasons: List[str] = []
        flags: List[str] = []
        confidence = 1.0
        
        # 0. Attribute Extraction
        extracted_attrs = AttributeExtractor.extract_attributes(listing.title, listing.description)
        listing.raw_attributes = extracted_attrs
        
        title_upper = str(listing.title or "").upper()
        combined_text = (str(listing.title or "") + " " + str(listing.description or "")).upper()
        
        # 1. Search / Trade Request
        if extracted_attrs.get('is_search_request'):
            return VerificationResult(
                status=ValidationStatus.REJECT,
                confidence_score=0.0,
                matched_attributes=extracted_attrs,
                rejection_reasons=["Search Request or Trade (Tausch/Suche)"]
            )
            
        # 2. Box-only / No-GPU scams
        if extracted_attrs.get('box_or_parts_only'):
            listing.is_scam_suspected = True
            listing.scam_reason = "Verdacht auf OVP / Leerkarton / Fehlende Kernkomponente"
            return VerificationResult(
                status=ValidationStatus.SCAM_SUSPECT,
                confidence_score=0.0,
                matched_attributes=extracted_attrs,
                rejection_reasons=["Box only / missing core component (e.g. Nur OVP / Ohne GPU)"]
            )
            
        # 3. Defect Detection
        if extracted_attrs.get('defect'):
            listing.is_scam_suspected = True
            listing.scam_reason = "Defekt / Bastlerware / Ersatzteilspender"
            return VerificationResult(
                status=ValidationStatus.SCAM_SUSPECT,
                confidence_score=0.0,
                matched_attributes=extracted_attrs,
                rejection_reasons=["Item is marked as defective/spares (Defekt/Bastler)"]
            )

        # 4. Price & VB Check
        # Negative prices rejection
        if listing.price is not None and listing.price < 0.0:
            return VerificationResult(
                status=ValidationStatus.REJECT,
                confidence_score=0.0,
                matched_attributes=extracted_attrs,
                rejection_reasons=["Invalid negative price (< 0€)"]
            )
            
        # Fake placeholder <= 5€
        if listing.is_fake_placeholder or (listing.price is not None and 0.0 < listing.price <= 5.0):
            listing.is_scam_suspected = True
            listing.scam_reason = "Scheinpreis / Fake-Platzhalter (<= 5€)"
            return VerificationResult(
                status=ValidationStatus.SCAM_SUSPECT,
                confidence_score=0.0,
                matched_attributes=extracted_attrs,
                rejection_reasons=["Suspiciously low price (<= 5€), fake VB placeholder"]
            )
            
        # Pure VB without any asking price
        if listing.needs_negotiation or listing.price == 0.0:
            flags.append("Pure VB without asking price")
            confidence -= 0.3
            
        # Valid asking price with VB (e.g. "200 € VB")
        if listing.is_vb and listing.price and listing.price > 5.0:
            flags.append(f"VB Asking Price: {listing.price} €")
            # Do NOT penalize confidence for having VB with asking price!

        # 5. Must Contain Tokens (Strict for model number)
        missing_mandatory = [t for t in spec.must_contain_tokens if t.upper() not in combined_text]
        if missing_mandatory:
            return VerificationResult(
                status=ValidationStatus.REJECT,
                confidence_score=0.0,
                matched_attributes=extracted_attrs,
                rejection_reasons=[f"Missing mandatory tokens: {missing_mandatory}"]
            )
            
        # Check if mandatory token is only in description, not in title
        for token in spec.must_contain_tokens:
            if token.upper() not in title_upper:
                flags.append(f"Token '{token}' only in description, missing in title")
                confidence -= 0.25

        # 6. Must Exclude Tokens (Forbidden tokens with negation handling: 'keine Ti')
        for token in spec.must_exclude_tokens:
            pattern = rf'\b{re.escape(token.upper())}\b'
            for m in re.finditer(pattern, title_upper):
                start = max(0, m.start() - 25)
                prefix = title_upper[start:m.start()]
                if re.search(r'\b(KEIN|KEINE|KEINEN|NICHT)\s*$', prefix):
                    continue  # Negated forbidden token (e.g. 'keine Ti')
                return VerificationResult(
                    status=ValidationStatus.REJECT,
                    confidence_score=0.0,
                    matched_attributes=extracted_attrs,
                    rejection_reasons=[f"Forbidden token found in title: {token}"]
                )

        # 7. Attribute Verification (e.g. VRAM)
        expected_vram = spec.expected_attributes.get('vram')
        if expected_vram and 'vram' in extracted_attrs:
            actual = extracted_attrs['vram']
            if actual not in expected_vram:
                reasons.append(f"VRAM Mismatch: Found {actual}GB, expected {expected_vram}GB")
                confidence -= 0.4
                flags.append("ambiguous_vram")

        # 8. Complete PC bundle detected when searching for single component
        if extracted_attrs.get('bundle_detected') and spec.type.value != "BUILD":
            flags.append("complete_pc_bundle_detected")
            confidence -= 0.35

        # Compute status
        status = ValidationStatus.PASS
        if confidence < 0.7 or reasons:
            status = ValidationStatus.REVIEW
        if confidence < 0.35:
            status = ValidationStatus.REJECT

        # 9. Optional synchronous AI Agent fallback (if passed directly)
        if status in [ValidationStatus.PASS, ValidationStatus.REVIEW] and ai_agent:
            ai_res = ai_agent.verify_listing(spec.name, listing.title, listing.description)
            if not ai_res.get("is_valid", False):
                status = ValidationStatus.REJECT
                confidence = 0.0
                reasons.append(f"AI Rejection: {ai_res.get('reason')}")
            else:
                confidence = max(confidence, 0.95)
                flags.append("AI Verified: True")

        return VerificationResult(
            status=status,
            confidence_score=max(0.0, round(confidence, 2)),
            matched_attributes=extracted_attrs,
            rejection_reasons=reasons,
            review_flags=flags
        )

    @staticmethod
    def should_escalate_to_llm(res: VerificationResult) -> bool:
        """Returns True if a listing requires Tier 2 active LLM verification / edit."""
        if res.status == ValidationStatus.REVIEW:
            return True
        if 0.35 <= res.confidence_score < 0.85:
            return True
        sensitive_flags = {"ambiguous_vram", "complete_pc_bundle_detected", "Token"}
        if any(any(sf in f for sf in sensitive_flags) for f in res.review_flags):
            return True
        return False

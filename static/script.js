document.addEventListener('DOMContentLoaded', () => {
    const todoForm = document.getElementById('todo-form');
    const todoInput = document.getElementById('todo-input');
    const todoList = document.getElementById('todo-list');
    const itemsLeft = document.getElementById('items-left');
    const filterButtons = document.querySelectorAll('.filter-btn');

    let todos = [];
    let currentFilter = 'all';

    // Fetch todos from API
    async function fetchTodos() {
        try {
            const response = await fetch('/api/todos');
            todos = await response.json();
            renderTodos();
        } catch (error) {
            console.error('Error fetching todos:', error);
        }
    }

    // Render todos to the DOM
    function renderTodos() {
        const filteredTodos = todos.filter(todo => {
            if (currentFilter === 'active') return !todo.completed;
            if (currentFilter === 'completed') return todo.completed;
            return true;
        });

        todoList.innerHTML = '';
        filteredTodos.forEach(todo => {
            const li = document.createElement('li');
            li.className = `todo-item ${todo.completed ? 'completed' : ''}`;
            li.innerHTML = `
                <div class="checkbox" onclick="toggleTodo(${todo.id}, ${todo.completed}, '${todo.title}')">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
                </div>
                <span>${todo.title}</span>
                <button class="delete-btn" onclick="deleteTodo(${todo.id})">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path><line x1="10" y1="11" x2="10" y2="17"></line><line x1="14" y1="11" x2="14" y2="17"></line></svg>
                </button>
            `;
            todoList.appendChild(li);
        });

        updateStats();
    }

    // Add new todo
    todoForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const title = todoInput.value.trim();
        if (!title) return;

        try {
            const response = await fetch('/api/todos', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ title, completed: false })
            });
            const newTodo = await response.json();
            todos.push(newTodo);
            todoInput.value = '';
            renderTodos();
        } catch (error) {
            console.error('Error adding todo:', error);
        }
    });

    // Toggle todo completion
    window.toggleTodo = async (id, currentStatus, title) => {
        try {
            const response = await fetch(`/api/todos/${id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ title, completed: !currentStatus })
            });
            const updatedTodo = await response.json();
            todos = todos.map(t => t.id === id ? updatedTodo : t);
            renderTodos();
        } catch (error) {
            console.error('Error toggling todo:', error);
        }
    };

    // Delete todo
    window.deleteTodo = async (id) => {
        try {
            await fetch(`/api/todos/${id}`, { method: 'DELETE' });
            todos = todos.filter(t => t.id !== id);
            renderTodos();
        } catch (error) {
            console.error('Error deleting todo:', error);
        }
    };

    // Update stats
    function updateStats() {
        const activeCount = todos.filter(t => !t.completed).length;
        itemsLeft.innerText = `${activeCount} item${activeCount !== 1 ? 's' : ''} left`;
    }

    // Filter handling
    filterButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            filterButtons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentFilter = btn.dataset.filter;
            renderTodos();
        });
    });

    // Initial fetch
    fetchTodos();
});

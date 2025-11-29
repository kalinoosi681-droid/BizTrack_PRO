// ========================================
// AI CHAT WIDGET - chat.js
// ========================================
document.addEventListener('DOMContentLoaded', function() {
    const toggleButton = document.getElementById('ai-chat-toggle-btn');
    const chatWidget = document.getElementById('ai-chat-widget');
    const clearButton = document.getElementById('ai-chat-clear-btn');
    const closeButton = document.getElementById('ai-chat-close-btn');
    const chatMessages = document.getElementById('ai-chat-messages');
    const chatForm = document.getElementById('ai-chat-form');
    const chatInput = document.getElementById('ai-chat-input');
    const submitButton = document.getElementById('ai-chat-submit-btn');
    const csrfTokenInput = document.querySelector('input[name="csrf_token"]');

    if (!toggleButton || !chatWidget || !chatForm || !clearButton) return;

    const suggestionChips = [
        "Top Sellers", "Low Stock", "Today's Sales", "Top Customers"
    ];

    // Toggle widget visibility
    toggleButton.addEventListener('click', () => {
        const isHidden = chatWidget.classList.toggle('hidden');
        if (!isHidden) {
            chatInput.focus();
            // Show suggestions only if chat is empty
            if (chatMessages.children.length === 0) {
                showSuggestionChips();
            }
        }
    });
    closeButton.addEventListener('click', () => chatWidget.classList.add('hidden'));

    // Clear chat history
    clearButton.addEventListener('click', () => {
        chatMessages.innerHTML = '';
        showSuggestionChips();
    });

    function showSuggestionChips() {
        const chipsContainer = document.createElement('div');
        chipsContainer.className = 'chat-suggestions';
        suggestionChips.forEach(text => {
            const chip = document.createElement('button');
            chip.className = 'suggestion-chip';
            chip.textContent = text;
            chip.onclick = () => {
                chatInput.value = text;
                chatForm.dispatchEvent(new Event('submit', { cancelable: true }));
            };
            chipsContainer.appendChild(chip);
        });
        chatMessages.appendChild(chipsContainer);
    }

    chatForm.addEventListener('submit', async function(event) {
        event.preventDefault();
        const query = chatInput.value.trim();
        if (!query) return;

        addChatMessage('user', query);
        chatInput.value = '';
        chatInput.disabled = true;
        submitButton.disabled = true;
        addChatMessage('ai', '<i class="fas fa-spinner fa-spin"></i>');

        // Clear suggestions on first message
        const suggestions = chatMessages.querySelector('.chat-suggestions');
        if (suggestions) {
            suggestions.remove();
        }

        try {
            const csrfToken = csrfTokenInput.value;
            const response = await fetch('/api/ai/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({ query: query })
            });

            chatMessages.removeChild(chatMessages.lastChild); // Remove "typing" indicator

            if (!response.ok) throw new Error(`Server error: ${response.statusText}`);

            const data = await response.json();
            addChatMessage('ai', data.response || 'Sorry, I could not understand that.');

        } catch (error) {
            console.error('AI Chat Error:', error);
            addChatMessage('ai', 'Sorry, I encountered an error. Please try again.');
        } finally {
            chatInput.disabled = false;
            submitButton.disabled = false;
            chatInput.focus();
        }
    });

    function addChatMessage(sender, message) {
        const messageElement = document.createElement('div');
        messageElement.classList.add('chat-message', `chat-message-${sender}`);
        messageElement.innerHTML = message; // Use innerHTML to render HTML from AI
        chatMessages.appendChild(messageElement);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
});
// ========================================
// ENHANCED AI CHAT WIDGET with Lesotho Intelligence
// ========================================
document.addEventListener('DOMContentLoaded', function() {
    const CURRENCY = 'M'; // Lesotho Maloti
    
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
        "How can I grow my business?",
        "Show low stock items",
        "Top customers",
        "Today's sales report",
        "Business advice",
        "Improve my margins"
    ];

    // Enhanced toggle with smooth animation
    toggleButton.addEventListener('click', () => {
        const isHidden = chatWidget.classList.toggle('hidden');
        
        if (!isHidden) {
            chatInput.focus();
            
            // Show welcome message and suggestions if chat is empty
            if (chatMessages.children.length === 0) {
                addChatMessage('ai', `
                    <div class="welcome-message">
                        <div class="mb-3">
                            <i class="bi bi-robot" style="font-size: 2.5rem; color: #667eea;"></i>
                        </div>
                        <h5 class="fw-bold">Dumela! 👋</h5>
                        <p class="mb-0">I'm your AI business assistant, powered by Lesotho market intelligence.</p>
                        <p class="text-muted small mt-2">How can I help your business thrive today?</p>
                    </div>
                `);
                showSuggestionChips();
            }
        }
        
        // Animate toggle button
        toggleButton.style.transform = isHidden ? 'scale(1)' : 'scale(0.9)';
        setTimeout(() => {
            toggleButton.style.transform = 'scale(1)';
        }, 200);
    });

    closeButton.addEventListener('click', () => {
        chatWidget.classList.add('hidden');
    });

    // Clear chat with confirmation for non-empty chats
    clearButton.addEventListener('click', () => {
        if (chatMessages.children.length > 0) {
            if (!confirm('Clear chat history?')) return;
        }
        
        chatMessages.innerHTML = '';
        
        // Show welcome message again
        addChatMessage('ai', `
            <div class="welcome-message">
                <div class="mb-3">
                    <i class="bi bi-robot" style="font-size: 2.5rem; color: #667eea;"></i>
                </div>
                <h5 class="fw-bold">Ready to assist! 🚀</h5>
                <p class="text-muted small mb-0">What would you like to know?</p>
            </div>
        `);
        showSuggestionChips();
    });

    function showSuggestionChips() {
        const chipsContainer = document.createElement('div');
        chipsContainer.className = 'chat-suggestions p-2';
        chipsContainer.innerHTML = '<small class="text-muted d-block mb-2">Try asking:</small>';
        
        suggestionChips.forEach(text => {
            const chip = document.createElement('button');
            chip.className = 'suggestion-chip btn btn-sm btn-outline-primary m-1';
            chip.style.borderRadius = '1rem';
            chip.style.fontSize = '0.8rem';
            chip.innerHTML = `<i class="bi bi-lightning-charge-fill me-1"></i>${text}`;
            chip.onclick = () => {
                chatInput.value = text;
                chatForm.dispatchEvent(new Event('submit', { cancelable: true }));
            };
            chipsContainer.appendChild(chip);
        });
        
        chatMessages.appendChild(chipsContainer);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    chatForm.addEventListener('submit', async function(event) {
        event.preventDefault();
        const query = chatInput.value.trim();
        if (!query) return;

        // Add user message
        addChatMessage('user', escapeHtml(query));
        chatInput.value = '';
        chatInput.disabled = true;
        submitButton.disabled = true;

        // Show typing indicator
        const typingId = addChatMessage('ai', `
            <div class="typing-indicator">
                <span></span><span></span><span></span>
            </div>
        `);

        // Clear suggestions on first real message
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

            // Remove typing indicator
            const typingElement = document.getElementById(typingId);
            if (typingElement) typingElement.remove();

            if (!response.ok) throw new Error(`Server error: ${response.statusText}`);

            const data = await response.json();
            
            // Process response to ensure Maloti currency
            let aiResponse = data.response || 'Sorry, I could not understand that.';
            aiResponse = aiResponse.replace(/\$(\d+\.?\d*)/g, `${CURRENCY}$1`);
            
            addChatMessage('ai', aiResponse);

        } catch (error) {
            console.error('AI Chat Error:', error);
            
            // Remove typing indicator
            const typingElement = document.getElementById(typingId);
            if (typingElement) typingElement.remove();
            
            addChatMessage('ai', `
                <div class="alert alert-danger mb-0" role="alert">
                    <i class="bi bi-exclamation-triangle me-2"></i>
                    <strong>Connection Error</strong><br>
                    I couldn't connect to the AI service. Please check your internet connection and try again.
                </div>
            `);
        } finally {
            chatInput.disabled = false;
            submitButton.disabled = false;
            chatInput.focus();
        }
    });

    function addChatMessage(sender, message) {
        const messageId = 'msg-' + Date.now();
        const messageElement = document.createElement('div');
        messageElement.id = messageId;
        messageElement.classList.add('chat-message', `chat-message-${sender}`);
        
        if (sender === 'user') {
            messageElement.innerHTML = `
                <div class="d-flex justify-content-end mb-2">
                    <div class="chat-bubble user-bubble">
                        ${message}
                    </div>
                </div>
            `;
        } else {
            messageElement.innerHTML = `
                <div class="d-flex justify-content-start mb-2">
                    <div class="chat-bubble ai-bubble">
                        ${message}
                    </div>
                </div>
            `;
        }
        
        chatMessages.appendChild(messageElement);
        
        // Smooth scroll to bottom
        chatMessages.scrollTo({
            top: chatMessages.scrollHeight,
            behavior: 'smooth'
        });
        
        return messageId;
    }

    // Utility function to escape HTML
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // Add keyboard shortcuts
    document.addEventListener('keydown', (e) => {
        // Ctrl/Cmd + K to open chat
        if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
            e.preventDefault();
            if (chatWidget.classList.contains('hidden')) {
                toggleButton.click();
            } else {
                chatInput.focus();
            }
        }
        
        // Escape to close chat
        if (e.key === 'Escape' && !chatWidget.classList.contains('hidden')) {
            closeButton.click();
        }
    });

    console.log('✅ AI Chat Widget initialized with Lesotho market intelligence');
});
/**
 * Authentication and User Management Integration for Live2D Healthcare AI
 * This file provides authentication, user profile, and personalized chat functionality
 */

class HealthcareAuthManager {
    constructor() {
        this.apiBase = window.location.origin.replace(':8080', ':8000'); // Healthcare AI backend
        this.sessionId = this.generateSessionId();
        this.userProfile = null;
        this.chatHistory = [];
        this.init();
    }

    async init() {
        // Remove any existing guest notifications first
        this.removeGuestNotifications();
        
        await this.checkAuthStatus();
        this.setupEventListeners();
        await this.loadUserProfile();
        await this.loadChatHistory();
        this.updateUI();
    }

    removeGuestNotifications() {
        // Remove any existing guest notification banners
        const notifications = document.querySelectorAll('.guest-notification, .notification-content');
        notifications.forEach(notification => {
            const parent = notification.closest('div');
            if (parent && (
                (parent.style.background && parent.style.background.includes('orange')) || 
                (parent.style.background && parent.style.background.includes('#f59e0b')) ||
                (parent.className && parent.className.includes('guest'))
            )) {
                parent.remove();
            } else {
                notification.remove();
            }
        });
        
        // Also remove any elements with guest notification text
        const allElements = document.querySelectorAll('*');
        allElements.forEach(element => {
            if (element.textContent && element.textContent.includes("You're chatting as a guest")) {
                element.remove();
            }
        });
    }

    generateSessionId() {
        const existing = localStorage.getItem('session_id');
        if (existing) return existing;
        
        const newSession = `live2d_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
        localStorage.setItem('session_id', newSession);
        return newSession;
    }

    async checkAuthStatus() {
        const token = localStorage.getItem('access_token');
        if (!token) {
            this.handleUnauthenticated();
            return false;
        }

        try {
            const response = await fetch(`${this.apiBase}/api/v1/auth/me`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });

            if (response.ok) {
                const userData = await response.json();
                this.userProfile = userData;
                return true;
            } else {
                this.handleAuthError();
                return false;
            }
        } catch (error) {
            console.error('Auth check failed:', error);
            this.handleAuthError();
            return false;
        }
    }

    handleUnauthenticated() {
        // Default to guest mode - no notifications or redirects
        localStorage.setItem('guest_mode', 'true');
        // No notification needed - guest mode is the default experience
    }

    handleAuthError() {
        // Clear invalid tokens
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        localStorage.removeItem('user_data');
        
        // Check if guest mode is acceptable
        this.handleUnauthenticated();
    }

    // Removed showGuestModeNotification - guest mode is now default without notifications

    async loadUserProfile() {
        if (!this.isAuthenticated()) return;

        try {
            const token = localStorage.getItem('access_token');
            const response = await fetch('/api/user/profile', {
                headers: { 'Authorization': `Bearer ${token}` }
            });

            if (response.ok) {
                const profileData = await response.json();
                this.userProfile = profileData.user;
                this.healthProfile = profileData.health_profile;
                this.preferences = profileData.preferences;
            }
        } catch (error) {
            console.error('Failed to load user profile:', error);
        }
    }

    async loadChatHistory() {
        if (!this.isAuthenticated()) return;

        try {
            const token = localStorage.getItem('access_token');
            const response = await fetch(`/api/user/chat-history?limit=10`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });

            if (response.ok) {
                const historyData = await response.json();
                this.chatHistory = historyData.chat_history || [];
                this.displayChatHistory();
            }
        } catch (error) {
            console.error('Failed to load chat history:', error);
        }
    }

    displayChatHistory() {
        if (!this.chatHistory.length) return;

        const chatContainer = document.getElementById('chat-container');
        if (!chatContainer) return;

        // Clear welcome message if present
        const welcomeMessage = chatContainer.querySelector('.welcome-message');
        if (welcomeMessage) welcomeMessage.remove();

        // Display recent conversations
        this.chatHistory.slice(-3).forEach(chat => {
            this.addMessage(chat.user_message, 'user', false);
            this.addMessage(chat.agent_response, 'bot', false);
        });

        // Scroll to bottom
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }

    async sendMessage(message) {
        if (!message.trim()) return;

        const headers = { 'Content-Type': 'application/json' };
        const token = localStorage.getItem('access_token');
        
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        const payload = {
            message: message,
            session_id: this.sessionId
        };

        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: headers,
                body: JSON.stringify(payload)
            });

            const data = await response.json();
            
            if (data.status === 'success') {
                // Handle personalized response
                this.handleChatResponse(data);
                return data;
            } else {
                throw new Error(data.error || 'Chat request failed');
            }
        } catch (error) {
            console.error('Chat error:', error);
            return {
                reply: "I'm having some technical difficulties. Please try again in a moment. 🤖",
                status: 'error'
            };
        }
    }

    handleChatResponse(data) {
        // Update Live2D avatar based on response
        if (data.live2d) {
            this.updateLive2DAvatar(data.live2d);
        }

        // Show personalization indicators
        if (data.personalized) {
            this.showPersonalizationIndicator(data.live2d);
        }

        // Update chat history
        this.chatHistory.push({
            user_message: "recent", // This would be the actual user message
            agent_response: data.reply,
            agent_type: data.live2d?.agent_type,
            timestamp: data.timestamp
        });
    }

    updateLive2DAvatar(live2dData) {
        try {
            // Update avatar model if needed
            if (live2dData.recommended_model && typeof swapModel === 'function') {
                swapModel(live2dData.recommended_model);
            }

            // Trigger emotion and gesture
            if (live2dData.emotion && typeof changeExpression === 'function') {
                changeExpression(live2dData.emotion);
            }

            if (live2dData.gesture && typeof triggerGesture === 'function') {
                triggerGesture(live2dData.gesture);
            }

            // Show agent information
            this.displayAgentInfo(live2dData);
        } catch (error) {
            console.error('Live2D update error:', error);
        }
    }

    displayAgentInfo(live2dData) {
        const agentIndicator = document.getElementById('agent-indicator') || this.createAgentIndicator();
        
        agentIndicator.innerHTML = `
            <div class="agent-info">
                <span class="agent-name">${live2dData.agent_name || live2dData.agent_name_en}</span>
                <span class="agent-confidence">Confidence: ${Math.round((live2dData.confidence || 0.8) * 100)}%</span>
            </div>
        `;
        
        // Add urgency indicator
        if (live2dData.urgency && live2dData.urgency !== 'low') {
            agentIndicator.classList.add(`urgency-${live2dData.urgency}`);
        }
    }

    createAgentIndicator() {
        const indicator = document.createElement('div');
        indicator.id = 'agent-indicator';
        indicator.className = 'agent-indicator';
        
        const header = document.querySelector('.header');
        if (header) {
            header.appendChild(indicator);
        }
        
        return indicator;
    }

    showPersonalizationIndicator(live2dData) {
        if (!this.isAuthenticated()) return;

        const indicator = document.createElement('div');
        indicator.className = 'personalization-indicator';
        indicator.innerHTML = `
            <span>🎯 Personalized for ${this.userProfile?.full_name || 'you'}</span>
        `;
        
        // Add to the last bot message
        const lastBotMessage = document.querySelector('.message.bot:last-child');
        if (lastBotMessage) {
            lastBotMessage.appendChild(indicator);
        }
    }

    async getUserDashboard() {
        if (!this.isAuthenticated()) return null;

        try {
            const token = localStorage.getItem('access_token');
            const response = await fetch('/api/user/dashboard', {
                headers: { 'Authorization': `Bearer ${token}` }
            });

            if (response.ok) {
                return await response.json();
            }
        } catch (error) {
            console.error('Failed to load dashboard:', error);
        }
        return null;
    }

    setupEventListeners() {
        // Override the original sendMessage function
        const originalSendMessage = window.sendMessage;
        window.sendMessage = async () => {
            const input = document.getElementById('textInput');
            const sendBtn = document.querySelector('.send-btn');
            const message = input.value.trim();
            
            if (!message) return;

            // Disable input and button
            input.disabled = true;
            sendBtn.disabled = true;
            
            // Add user message to chat
            this.addMessage(message, 'user');
            input.value = '';
            this.showTypingIndicator();

            try {
                // Send message through our auth system
                const response = await this.sendMessage(message);
                
                // Add bot response
                this.hideTypingIndicator();
                this.addMessage(response.reply, 'bot');
            } catch (error) {
                this.hideTypingIndicator();
                this.addMessage("I'm having some technical difficulties. Please try again.", 'bot');
            } finally {
                // Re-enable input and button
                input.disabled = false;
                sendBtn.disabled = false;
                input.focus();
            }
        };

        // Add logout functionality
        this.addLogoutButton();
        
        // Add profile button
        this.addProfileButton();
    }

    addMessage(text, sender, animate = true) {
        // Use existing addMessage function if available, otherwise create our own
        if (typeof window.addMessage === 'function') {
            window.addMessage(text, sender);
        } else {
            this.createMessage(text, sender, animate);
        }
    }

    createMessage(text, sender, animate = true) {
        const chatContainer = document.getElementById('chat-container');
        if (!chatContainer) return;

        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}`;
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        contentDiv.textContent = text;
        
        messageDiv.appendChild(contentDiv);
        chatContainer.appendChild(messageDiv);
        
        if (animate) {
            messageDiv.style.opacity = '0';
            messageDiv.style.transform = 'translateY(10px)';
            
            setTimeout(() => {
                messageDiv.style.transition = 'all 0.3s ease';
                messageDiv.style.opacity = '1';
                messageDiv.style.transform = 'translateY(0)';
            }, 100);
        }
        
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }

    showTypingIndicator() {
        if (typeof window.showTypingIndicator === 'function') {
            window.showTypingIndicator();
        }
    }

    hideTypingIndicator() {
        if (typeof window.hideTypingIndicator === 'function') {
            window.hideTypingIndicator();
        }
    }

    addLogoutButton() {
        if (!this.isAuthenticated()) return;

        const header = document.querySelector('.header');
        if (!header || header.querySelector('.logout-btn')) return;

        const logoutBtn = document.createElement('button');
        logoutBtn.className = 'logout-btn';
        logoutBtn.innerHTML = '🚪 Logout';
        logoutBtn.onclick = () => this.logout();
        
        header.appendChild(logoutBtn);
    }

    addProfileButton() {
        if (!this.isAuthenticated()) return;

        const header = document.querySelector('.header');
        if (!header || header.querySelector('.profile-btn')) return;

        const profileBtn = document.createElement('button');
        profileBtn.className = 'profile-btn';
        profileBtn.innerHTML = '👤 Profile';
        profileBtn.onclick = () => this.showProfile();
        
        header.appendChild(profileBtn);
    }

    async logout() {
        try {
            const token = localStorage.getItem('access_token');
            if (token) {
                await fetch(`${this.apiBase}/api/v1/auth/logout`, {
                    method: 'POST',
                    headers: { 'Authorization': `Bearer ${token}` }
                });
            }
        } catch (error) {
            console.error('Logout error:', error);
        } finally {
            // Clear local storage
            localStorage.removeItem('access_token');
            localStorage.removeItem('refresh_token');
            localStorage.removeItem('user_data');
            localStorage.removeItem('session_id');
            localStorage.removeItem('guest_mode');
            
            // Redirect to auth page
            window.location.href = '/live2d/auth';
        }
    }

    async showProfile() {
        const dashboardData = await this.getUserDashboard();
        if (!dashboardData) return;

        // Create modal for profile display
        const modal = document.createElement('div');
        modal.className = 'profile-modal';
        modal.innerHTML = `
            <div class="modal-content">
                <div class="modal-header">
                    <h2>Health Profile</h2>
                    <button class="close-btn" onclick="this.closest('.profile-modal').remove()">×</button>
                </div>
                <div class="modal-body">
                    <div class="profile-section">
                        <h3>👤 Personal Information</h3>
                        <p><strong>Name:</strong> ${dashboardData.dashboard.user_info.name}</p>
                        <p><strong>Email:</strong> ${dashboardData.dashboard.user_info.email}</p>
                        <p><strong>Language:</strong> ${dashboardData.dashboard.user_info.language}</p>
                    </div>
                    
                    <div class="profile-section">
                        <h3>🏥 Health Summary</h3>
                        <p><strong>Health Profile:</strong> ${dashboardData.dashboard.health_summary.has_profile ? 'Complete' : 'Incomplete'}</p>
                        <p><strong>Medications:</strong> ${dashboardData.dashboard.health_summary.current_medications}</p>
                        <p><strong>Conditions:</strong> ${dashboardData.dashboard.health_summary.chronic_conditions}</p>
                        <p><strong>Health Goals:</strong> ${dashboardData.dashboard.health_summary.health_goals}</p>
                    </div>
                    
                    <div class="profile-section">
                        <h3>💬 Activity Summary</h3>
                        <p><strong>Total Conversations:</strong> ${dashboardData.dashboard.activity_summary.total_conversations}</p>
                        <p><strong>This Week:</strong> ${dashboardData.dashboard.activity_summary.recent_conversations}</p>
                    </div>
                    
                    <div class="profile-section">
                        <h3>💡 Health Insights</h3>
                        ${dashboardData.dashboard.health_insights.map(insight => `<p>• ${insight}</p>`).join('')}
                    </div>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
    }

    updateUI() {
        // Add authentication status styles
        const styles = document.createElement('style');
        styles.textContent = `
            .guest-notification {
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                background: #f59e0b;
                color: white;
                padding: 10px;
                text-align: center;
                z-index: 1000;
            }
            
            .notification-content {
                display: flex;
                justify-content: space-between;
                align-items: center;
                max-width: 1200px;
                margin: 0 auto;
            }
            
            .notification-content a {
                color: white;
                text-decoration: underline;
            }
            
            .logout-btn, .profile-btn {
                background: var(--primary);
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                cursor: pointer;
                margin-left: 10px;
                font-size: 14px;
            }
            
            .logout-btn:hover, .profile-btn:hover {
                opacity: 0.8;
            }
            
            .agent-indicator {
                display: flex;
                flex-direction: column;
                font-size: 12px;
                color: var(--muted-foreground);
            }
            
            .agent-info {
                display: flex;
                gap: 10px;
            }
            
            .urgency-high .agent-info {
                color: var(--destructive);
                font-weight: bold;
            }
            
            .personalization-indicator {
                font-size: 11px;
                color: var(--primary);
                margin-top: 5px;
                font-style: italic;
            }
            
            .profile-modal {
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(0, 0, 0, 0.5);
                display: flex;
                justify-content: center;
                align-items: center;
                z-index: 1000;
            }
            
            .modal-content {
                background: var(--card);
                color: var(--card-foreground);
                border-radius: 12px;
                max-width: 600px;
                width: 90%;
                max-height: 80vh;
                overflow-y: auto;
            }
            
            .modal-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 20px;
                border-bottom: 1px solid var(--border);
            }
            
            .modal-body {
                padding: 20px;
            }
            
            .profile-section {
                margin-bottom: 20px;
                padding-bottom: 15px;
                border-bottom: 1px solid var(--border);
            }
            
            .profile-section h3 {
                margin-bottom: 10px;
                color: var(--primary);
            }
            
            .close-btn {
                background: none;
                border: none;
                font-size: 24px;
                cursor: pointer;
                color: var(--foreground);
            }
        `;
        document.head.appendChild(styles);
    }

    isAuthenticated() {
        return !!localStorage.getItem('access_token');
    }

    isGuest() {
        return localStorage.getItem('guest_mode') === 'true';
    }
}

// Initialize the auth manager when the page loads
window.addEventListener('load', () => {
    window.healthcareAuth = new HealthcareAuthManager();
});

// Export for global access
window.HealthcareAuthManager = HealthcareAuthManager;

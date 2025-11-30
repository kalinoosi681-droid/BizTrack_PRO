# ========================================
# auth_models.py
# ========================================
from flask_login import UserMixin
from .biztrack_db import get_user_by_id

class User(UserMixin):
    """
    User model for Flask-Login authentication.
    This wraps the user dictionary from the database.
    """
    def __init__(self, user_dict):
        """
        Initialize user from database dictionary.
        
        Args:
            user_dict: Dictionary with keys: id, username, password, role, etc.
        """
        if not user_dict:
            raise ValueError("User dictionary cannot be None")
        
        self.id = user_dict['id']
        self.username = user_dict['username']
        self.password = user_dict['password']
        self.role = user_dict['role']
        self.created_at = user_dict.get('created_at')
        self.failed_attempts = user_dict.get('failed_attempts', 0)
        self.locked_until = user_dict.get('locked_until')
        self.reset_token = user_dict.get('reset_token')
        self.reset_token_expiration = user_dict.get('reset_token_expiration')
    
    def get_id(self):
        """
        Flask-Login requires this method to return the user ID as a string.
        """
        return str(self.id)
    
    def is_admin(self):
        """Check if user has admin role."""
        return self.role == 'admin'
    
    def is_locked(self):
        """Check if user account is locked."""
        if not self.locked_until:
            return False
        
        from datetime import datetime
        try:
            locked_until = datetime.fromisoformat(self.locked_until)
            return datetime.now() < locked_until
        except:
            return False
    
    @staticmethod
    def get(user_id):
        """
        Load a user by ID. Required by Flask-Login.
        
        Args:
            user_id: The user's ID (as string or int)
            
        Returns:
            User object or None if not found
        """
        try:
            user_id = int(user_id)
        except (ValueError, TypeError):
            return None
        
        user_dict = get_user_by_id(user_id)
        
        if not user_dict:
            return None
        
        return User(user_dict)
    
    def __repr__(self):
        return f'<User {self.username}>'
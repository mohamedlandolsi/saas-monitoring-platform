"""
User model for authentication and user management
"""
from datetime import datetime
from bson import ObjectId
from typing import Dict, Optional
import bcrypt


class User:
    """Model for user authentication stored in MongoDB"""
    
    def __init__(self, mongo_client):
        """
        Initialize User model with MongoDB client
        
        Args:
            mongo_client: PyMongo client instance
        """
        self.client = mongo_client
        self.db = mongo_client['saas_monitoring']
        self.collection = self.db['users']
        
        # Create indexes for better performance
        try:
            self.collection.create_index([('username', 1)], unique=True)
            self.collection.create_index([('email', 1)], unique=True)
            self.collection.create_index([('created_at', -1)])
        except Exception as e:
            print(f"Warning: Could not create indexes: {str(e)}")
    
    def create(
        self,
        username: str,
        email: str,
        password: str,
        full_name: Optional[str] = None
    ) -> Optional[str]:
        """
        Create a new user with hashed password
        
        Args:
            username: Unique username
            email: Unique email address
            password: Plain text password (will be hashed)
            full_name: Optional full name
        
        Returns:
            str: Inserted user ID, or None if error
        
        Raises:
            ValueError: If username or email already exists
        """
        try:
            # Validate inputs
            if not username or not email or not password:
                raise ValueError("Username, email, and password are required")
            
            # Check if username already exists
            if self.collection.find_one({'username': username}):
                raise ValueError(f"Username '{username}' already exists")
            
            # Check if email already exists
            if self.collection.find_one({'email': email}):
                raise ValueError(f"Email '{email}' already exists")
            
            # Hash password with bcrypt
            password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
            
            # Create user document
            document = {
                'username': username,
                'email': email,
                'password_hash': password_hash,
                'full_name': full_name or '',
                'created_at': datetime.utcnow().isoformat(),
                'last_login': None,
                'is_active': True,
                'is_admin': False
            }
            
            result = self.collection.insert_one(document)
            return str(result.inserted_id)
            
        except ValueError:
            # Re-raise validation errors
            raise
        except Exception as e:
            print(f"Error creating user: {str(e)}")
            return None
    
    def authenticate(self, username: str, password: str) -> Optional[Dict]:
        """
        Authenticate a user with username and password
        
        Args:
            username: Username or email
            password: Plain text password
        
        Returns:
            Dict: User document (without password_hash) if authenticated, None otherwise
        """
        try:
            # Find user by username or email
            user = self.collection.find_one({
                '$or': [
                    {'username': username},
                    {'email': username}
                ]
            })
            
            if not user:
                return None
            
            # Check if user is active
            if not user.get('is_active', True):
                return None
            
            # Verify password
            password_hash = user.get('password_hash')
            if not password_hash:
                return None
            
            if not bcrypt.checkpw(password.encode('utf-8'), password_hash):
                return None
            
            # Update last login timestamp
            self.collection.update_one(
                {'_id': user['_id']},
                {'$set': {'last_login': datetime.utcnow().isoformat()}}
            )
            
            # Remove password hash from returned user
            user.pop('password_hash', None)
            user['_id'] = str(user['_id'])
            
            return user
            
        except Exception as e:
            print(f"Error authenticating user: {str(e)}")
            return None
    
    def get_by_id(self, user_id: str) -> Optional[Dict]:
        """
        Get user by ID
        
        Args:
            user_id: User document ID
        
        Returns:
            Dict: User document (without password_hash), or None if not found
        """
        try:
            user = self.collection.find_one({'_id': ObjectId(user_id)})
            
            if not user:
                return None
            
            # Remove password hash
            user.pop('password_hash', None)
            user['_id'] = str(user['_id'])
            
            return user
            
        except Exception as e:
            print(f"Error getting user by ID: {str(e)}")
            return None
    
    def get_by_username(self, username: str) -> Optional[Dict]:
        """
        Get user by username
        
        Args:
            username: Username
        
        Returns:
            Dict: User document (without password_hash), or None if not found
        """
        try:
            user = self.collection.find_one({'username': username})
            
            if not user:
                return None
            
            # Remove password hash
            user.pop('password_hash', None)
            user['_id'] = str(user['_id'])
            
            return user
            
        except Exception as e:
            print(f"Error getting user by username: {str(e)}")
            return None
    
    def get_by_email(self, email: str) -> Optional[Dict]:
        """
        Get user by email
        
        Args:
            email: Email address
        
        Returns:
            Dict: User document (without password_hash), or None if not found
        """
        try:
            user = self.collection.find_one({'email': email})
            
            if not user:
                return None
            
            # Remove password hash
            user.pop('password_hash', None)
            user['_id'] = str(user['_id'])
            
            return user
            
        except Exception as e:
            print(f"Error getting user by email: {str(e)}")
            return None
    
    def update_password(self, user_id: str, new_password: str) -> bool:
        """
        Update user password
        
        Args:
            user_id: User document ID
            new_password: New plain text password (will be hashed)
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Hash new password
            password_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
            
            result = self.collection.update_one(
                {'_id': ObjectId(user_id)},
                {'$set': {'password_hash': password_hash}}
            )
            
            return result.modified_count > 0
            
        except Exception as e:
            print(f"Error updating password: {str(e)}")
            return False
    
    def update_profile(
        self,
        user_id: str,
        email: Optional[str] = None,
        full_name: Optional[str] = None
    ) -> bool:
        """
        Update user profile information
        
        Args:
            user_id: User document ID
            email: New email (optional)
            full_name: New full name (optional)
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            update_fields = {}
            
            if email is not None:
                # Check if email is already taken by another user
                existing = self.collection.find_one({
                    'email': email,
                    '_id': {'$ne': ObjectId(user_id)}
                })
                if existing:
                    raise ValueError(f"Email '{email}' is already taken")
                update_fields['email'] = email
            
            if full_name is not None:
                update_fields['full_name'] = full_name
            
            if not update_fields:
                return False
            
            result = self.collection.update_one(
                {'_id': ObjectId(user_id)},
                {'$set': update_fields}
            )
            
            return result.modified_count > 0
            
        except ValueError:
            raise
        except Exception as e:
            print(f"Error updating profile: {str(e)}")
            return False
    
    def deactivate(self, user_id: str) -> bool:
        """
        Deactivate a user account
        
        Args:
            user_id: User document ID
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            result = self.collection.update_one(
                {'_id': ObjectId(user_id)},
                {'$set': {'is_active': False}}
            )
            
            return result.modified_count > 0
            
        except Exception as e:
            print(f"Error deactivating user: {str(e)}")
            return False
    
    def activate(self, user_id: str) -> bool:
        """
        Activate a user account
        
        Args:
            user_id: User document ID
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            result = self.collection.update_one(
                {'_id': ObjectId(user_id)},
                {'$set': {'is_active': True}}
            )
            
            return result.modified_count > 0
            
        except Exception as e:
            print(f"Error activating user: {str(e)}")
            return False
    
    def delete(self, user_id: str) -> bool:
        """
        Delete a user account
        
        Args:
            user_id: User document ID
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            result = self.collection.delete_one({'_id': ObjectId(user_id)})
            return result.deleted_count > 0
            
        except Exception as e:
            print(f"Error deleting user: {str(e)}")
            return False
    
    def get_all_users(self, limit: int = 100, skip: int = 0) -> list:
        """
        Get all users (admin function)
        
        Args:
            limit: Maximum number of users to return
            skip: Number of users to skip
        
        Returns:
            list: List of user documents (without password_hash)
        """
        try:
            users = list(
                self.collection.find()
                .sort('created_at', -1)
                .skip(skip)
                .limit(limit)
            )
            
            # Remove password hashes and convert ObjectId
            for user in users:
                user.pop('password_hash', None)
                user['_id'] = str(user['_id'])
            
            return users
            
        except Exception as e:
            print(f"Error getting all users: {str(e)}")
            return []
    
    def count_users(self) -> int:
        """
        Count total number of users
        
        Returns:
            int: Total user count
        """
        try:
            return self.collection.count_documents({})
        except Exception as e:
            print(f"Error counting users: {str(e)}")
            return 0

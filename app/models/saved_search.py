"""
SavedSearch model for storing user's saved search queries in MongoDB
"""
from datetime import datetime
from bson import ObjectId
from typing import Dict, List, Optional


class SavedSearch:
    """Model for saved searches stored in MongoDB"""
    
    def __init__(self, mongo_client):
        """
        Initialize SavedSearch model with MongoDB client
        
        Args:
            mongo_client: PyMongo client instance
        """
        self.client = mongo_client
        self.db = mongo_client['saas_monitoring']
        self.collection = self.db['saved_searches']
        
        # Create indexes for better performance
        try:
            self.collection.create_index([('user', 1), ('name', 1)], unique=True)
            self.collection.create_index([('user', 1), ('created_at', -1)])
            self.collection.create_index([('last_used', -1)])
        except Exception as e:
            print(f"Warning: Could not create indexes: {str(e)}")
    
    def save(
        self,
        name: str,
        filters: Dict,
        user: Optional[str] = None,
        description: Optional[str] = None
    ) -> Optional[str]:
        """
        Save a search query with filters
        
        Args:
            name: Name for the saved search
            filters: Search filters (query, level, status_code, etc.)
            user: User identifier (optional, defaults to 'anonymous')
            description: Optional description of the search
        
        Returns:
            str: Inserted document ID, or None if error
        """
        document = {
            'name': name,
            'filters': filters,
            'user': user or 'anonymous',
            'description': description or '',
            'created_at': datetime.utcnow().isoformat(),
            'last_used': datetime.utcnow().isoformat(),
            'use_count': 0
        }
        
        try:
            result = self.collection.insert_one(document)
            return str(result.inserted_id)
        except Exception as e:
            print(f"Error saving search: {str(e)}")
            return None
    
    def get_by_user(self, user: Optional[str] = None, limit: int = 50) -> List[Dict]:
        """
        Get all saved searches for a user
        
        Args:
            user: User identifier (defaults to 'anonymous')
            limit: Maximum number of results
        
        Returns:
            List[Dict]: List of saved search documents
        """
        try:
            searches = list(
                self.collection.find({'user': user or 'anonymous'})
                .sort('last_used', -1)
                .limit(limit)
            )
            
            # Convert ObjectId to string
            for search in searches:
                search['_id'] = str(search['_id'])
            
            return searches
        except Exception as e:
            print(f"Error fetching saved searches: {str(e)}")
            return []
    
    def get_by_id(self, search_id: str) -> Optional[Dict]:
        """
        Get a saved search by ID
        
        Args:
            search_id: Search document ID
        
        Returns:
            Dict: Saved search document or None
        """
        try:
            search = self.collection.find_one({'_id': ObjectId(search_id)})
            if search:
                search['_id'] = str(search['_id'])
                return search
            return None
        except Exception as e:
            print(f"Error fetching saved search: {str(e)}")
            return None
    
    def update_last_used(self, search_id: str) -> bool:
        """
        Update the last_used timestamp and increment use_count
        
        Args:
            search_id: Search document ID
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            result = self.collection.update_one(
                {'_id': ObjectId(search_id)},
                {
                    '$set': {'last_used': datetime.utcnow().isoformat()},
                    '$inc': {'use_count': 1}
                }
            )
            return result.modified_count > 0
        except Exception as e:
            print(f"Error updating last_used: {str(e)}")
            return False
    
    def delete(self, search_id: str, user: Optional[str] = None) -> bool:
        """
        Delete a saved search
        
        Args:
            search_id: Search document ID
            user: User identifier (for authorization)
        
        Returns:
            bool: True if deleted, False otherwise
        """
        try:
            query = {'_id': ObjectId(search_id)}
            if user:
                query['user'] = user
            
            result = self.collection.delete_one(query)
            return result.deleted_count > 0
        except Exception as e:
            print(f"Error deleting saved search: {str(e)}")
            return False
    
    def update(
        self,
        search_id: str,
        name: Optional[str] = None,
        filters: Optional[Dict] = None,
        description: Optional[str] = None,
        user: Optional[str] = None
    ) -> bool:
        """
        Update a saved search
        
        Args:
            search_id: Search document ID
            name: New name (optional)
            filters: New filters (optional)
            description: New description (optional)
            user: User identifier (for authorization)
        
        Returns:
            bool: True if updated, False otherwise
        """
        try:
            query = {'_id': ObjectId(search_id)}
            if user:
                query['user'] = user
            
            update_fields = {}
            if name is not None:
                update_fields['name'] = name
            if filters is not None:
                update_fields['filters'] = filters
            if description is not None:
                update_fields['description'] = description
            
            if not update_fields:
                return False
            
            result = self.collection.update_one(
                query,
                {'$set': update_fields}
            )
            return result.modified_count > 0
        except Exception as e:
            print(f"Error updating saved search: {str(e)}")
            return False
    
    def get_most_used(self, user: Optional[str] = None, limit: int = 10) -> List[Dict]:
        """
        Get most frequently used saved searches
        
        Args:
            user: User identifier (optional)
            limit: Maximum number of results
        
        Returns:
            List[Dict]: List of saved search documents
        """
        try:
            query = {}
            if user:
                query['user'] = user
            
            searches = list(
                self.collection.find(query)
                .sort('use_count', -1)
                .limit(limit)
            )
            
            # Convert ObjectId to string
            for search in searches:
                search['_id'] = str(search['_id'])
            
            return searches
        except Exception as e:
            print(f"Error fetching most used searches: {str(e)}")
            return []
    
    def search_by_name(self, name_pattern: str, user: Optional[str] = None) -> List[Dict]:
        """
        Search for saved searches by name pattern
        
        Args:
            name_pattern: Pattern to match in search name
            user: User identifier (optional)
        
        Returns:
            List[Dict]: List of matching saved search documents
        """
        try:
            query = {'name': {'$regex': name_pattern, '$options': 'i'}}
            if user:
                query['user'] = user
            
            searches = list(
                self.collection.find(query)
                .sort('last_used', -1)
            )
            
            # Convert ObjectId to string
            for search in searches:
                search['_id'] = str(search['_id'])
            
            return searches
        except Exception as e:
            print(f"Error searching saved searches: {str(e)}")
            return []
    
    def get_statistics(self, user: Optional[str] = None) -> Dict:
        """
        Get statistics about saved searches
        
        Args:
            user: User identifier (optional)
        
        Returns:
            Dict: Statistics including total count, most used, etc.
        """
        try:
            query = {}
            if user:
                query['user'] = user
            
            total_count = self.collection.count_documents(query)
            
            if total_count == 0:
                return {
                    'total_searches': 0,
                    'total_uses': 0,
                    'avg_uses': 0
                }
            
            pipeline = [
                {'$match': query},
                {'$group': {
                    '_id': None,
                    'total_uses': {'$sum': '$use_count'},
                    'avg_uses': {'$avg': '$use_count'}
                }}
            ]
            
            result = list(self.collection.aggregate(pipeline))
            
            if result:
                stats = result[0]
                return {
                    'total_searches': total_count,
                    'total_uses': stats.get('total_uses', 0),
                    'avg_uses': round(stats.get('avg_uses', 0), 2)
                }
            else:
                return {
                    'total_searches': total_count,
                    'total_uses': 0,
                    'avg_uses': 0
                }
        except Exception as e:
            print(f"Error getting statistics: {str(e)}")
            return {
                'total_searches': 0,
                'total_uses': 0,
                'avg_uses': 0
            }

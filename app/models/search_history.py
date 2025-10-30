"""
SearchHistory model for tracking search queries in MongoDB
"""
from datetime import datetime
from bson import ObjectId
from typing import Dict, List, Optional


class SearchHistory:
    """Model for search history stored in MongoDB"""
    
    def __init__(self, mongo_client):
        """
        Initialize SearchHistory model with MongoDB client
        
        Args:
            mongo_client: PyMongo client instance
        """
        self.client = mongo_client
        self.db = mongo_client['saas_monitoring']
        self.collection = self.db['search_history']
        
        # Create indexes for better performance
        try:
            self.collection.create_index([('timestamp', -1)])
            self.collection.create_index([('user', 1), ('timestamp', -1)])
        except Exception as e:
            print(f"Warning: Could not create indexes: {str(e)}")
    
    def save(
        self,
        query: str,
        filters: Dict,
        user: Optional[str] = None,
        results_count: int = 0,
        execution_time_ms: Optional[float] = None
    ) -> str:
        """
        Save a search query to history
        
        Args:
            query: Search query text
            filters: Applied filters (level, status_code, server, etc.)
            user: User identifier (optional)
            results_count: Number of results returned
            execution_time_ms: Query execution time in milliseconds
        
        Returns:
            str: Inserted document ID
        """
        document = {
            'query': query,
            'filters': filters,
            'user': user or 'anonymous',
            'results_count': results_count,
            'execution_time_ms': execution_time_ms,
            'timestamp': datetime.utcnow().isoformat(),
            'date': datetime.utcnow().strftime('%Y-%m-%d')
        }
        
        try:
            result = self.collection.insert_one(document)
            return str(result.inserted_id)
        except Exception as e:
            print(f"Error saving search history: {str(e)}")
            return None
    
    def get_recent(self, limit: int = 10, user: Optional[str] = None) -> List[Dict]:
        """
        Get recent search queries
        
        Args:
            limit: Maximum number of results to return
            user: Optional user filter
        
        Returns:
            List[Dict]: List of search history documents
        """
        try:
            query = {}
            if user:
                query['user'] = user
            
            searches = list(
                self.collection.find(query)
                .sort('timestamp', -1)
                .limit(limit)
            )
            
            # Convert ObjectId to string
            for search in searches:
                search['_id'] = str(search['_id'])
            
            return searches
        except Exception as e:
            print(f"Error fetching recent searches: {str(e)}")
            return []
    
    def get_by_user(self, user: str, limit: int = 50) -> List[Dict]:
        """
        Get search history for a specific user
        
        Args:
            user: User identifier
            limit: Maximum number of results
        
        Returns:
            List[Dict]: List of search history documents
        """
        try:
            searches = list(
                self.collection.find({'user': user})
                .sort('timestamp', -1)
                .limit(limit)
            )
            
            # Convert ObjectId to string
            for search in searches:
                search['_id'] = str(search['_id'])
            
            return searches
        except Exception as e:
            print(f"Error fetching user searches: {str(e)}")
            return []
    
    def get_popular_queries(self, limit: int = 10, days: int = 7) -> List[Dict]:
        """
        Get most popular search queries
        
        Args:
            limit: Maximum number of results
            days: Number of days to look back
        
        Returns:
            List[Dict]: List of popular queries with counts
        """
        try:
            from datetime import timedelta
            
            cutoff_date = (datetime.utcnow() - timedelta(days=days)).isoformat()
            
            pipeline = [
                {'$match': {'timestamp': {'$gte': cutoff_date}}},
                {'$group': {
                    '_id': '$query',
                    'count': {'$sum': 1},
                    'avg_results': {'$avg': '$results_count'},
                    'last_used': {'$max': '$timestamp'}
                }},
                {'$sort': {'count': -1}},
                {'$limit': limit}
            ]
            
            results = list(self.collection.aggregate(pipeline))
            return results
        except Exception as e:
            print(f"Error fetching popular queries: {str(e)}")
            return []
    
    def get_statistics(self, days: int = 30) -> Dict:
        """
        Get search statistics
        
        Args:
            days: Number of days to analyze
        
        Returns:
            Dict: Statistics including total searches, unique users, etc.
        """
        try:
            from datetime import timedelta
            
            cutoff_date = (datetime.utcnow() - timedelta(days=days)).isoformat()
            
            pipeline = [
                {'$match': {'timestamp': {'$gte': cutoff_date}}},
                {'$group': {
                    '_id': None,
                    'total_searches': {'$sum': 1},
                    'unique_users': {'$addToSet': '$user'},
                    'avg_results': {'$avg': '$results_count'},
                    'avg_execution_time': {'$avg': '$execution_time_ms'}
                }}
            ]
            
            result = list(self.collection.aggregate(pipeline))
            
            if result:
                stats = result[0]
                return {
                    'total_searches': stats.get('total_searches', 0),
                    'unique_users': len(stats.get('unique_users', [])),
                    'avg_results': round(stats.get('avg_results', 0), 2),
                    'avg_execution_time_ms': round(stats.get('avg_execution_time', 0), 2),
                    'period_days': days
                }
            else:
                return {
                    'total_searches': 0,
                    'unique_users': 0,
                    'avg_results': 0,
                    'avg_execution_time_ms': 0,
                    'period_days': days
                }
        except Exception as e:
            print(f"Error getting statistics: {str(e)}")
            return {
                'total_searches': 0,
                'unique_users': 0,
                'avg_results': 0,
                'avg_execution_time_ms': 0,
                'period_days': days
            }
    
    def delete_old_searches(self, days: int = 90) -> int:
        """
        Delete old search history entries
        
        Args:
            days: Delete entries older than this many days
        
        Returns:
            int: Number of deleted documents
        """
        try:
            from datetime import timedelta
            
            cutoff_date = (datetime.utcnow() - timedelta(days=days)).isoformat()
            
            result = self.collection.delete_many({'timestamp': {'$lt': cutoff_date}})
            return result.deleted_count
        except Exception as e:
            print(f"Error deleting old searches: {str(e)}")
            return 0
    
    def get_by_date_range(
        self,
        start_date: str,
        end_date: str,
        user: Optional[str] = None
    ) -> List[Dict]:
        """
        Get searches within a date range
        
        Args:
            start_date: Start date (ISO format)
            end_date: End date (ISO format)
            user: Optional user filter
        
        Returns:
            List[Dict]: List of search history documents
        """
        try:
            query = {
                'timestamp': {
                    '$gte': start_date,
                    '$lte': end_date
                }
            }
            
            if user:
                query['user'] = user
            
            searches = list(
                self.collection.find(query)
                .sort('timestamp', -1)
            )
            
            # Convert ObjectId to string
            for search in searches:
                search['_id'] = str(search['_id'])
            
            return searches
        except Exception as e:
            print(f"Error fetching searches by date range: {str(e)}")
            return []

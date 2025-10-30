"""
File model for managing uploaded files in MongoDB
"""
from datetime import datetime
from bson import ObjectId
from typing import Dict, List, Optional


class File:
    """Model for file metadata stored in MongoDB"""
    
    def __init__(self, mongo_client):
        """
        Initialize File model with MongoDB client
        
        Args:
            mongo_client: PyMongo client instance
        """
        self.client = mongo_client
        self.db = mongo_client['saas_monitoring']
        self.collection = self.db['files']
    
    def create(
        self,
        filename: str,
        saved_as: str,
        file_type: str,
        file_size: int,
        log_count: int = 0,
        status: str = 'pending',
        metadata: Optional[Dict] = None
    ) -> str:
        """
        Create a new file document in MongoDB
        
        Args:
            filename: Original filename
            saved_as: Unique filename saved on disk
            file_type: File type (csv, json)
            file_size: Size in bytes
            log_count: Number of logs in file
            status: Upload status (pending, processing, completed, error)
            metadata: Additional metadata dictionary
        
        Returns:
            str: Inserted document ID
        """
        document = {
            'filename': filename,
            'saved_as': saved_as,
            'file_type': file_type,
            'file_size': file_size,
            'log_count': log_count,
            'status': status,
            'upload_date': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat(),
            'metadata': metadata or {}
        }
        
        result = self.collection.insert_one(document)
        return str(result.inserted_id)
    
    def get_all(self, sort_by: str = 'upload_date', ascending: bool = False) -> List[Dict]:
        """
        Get all files sorted by specified field
        
        Args:
            sort_by: Field to sort by (default: upload_date)
            ascending: Sort direction (default: False for descending)
        
        Returns:
            List[Dict]: List of file documents
        """
        sort_direction = 1 if ascending else -1
        files = list(self.collection.find({}).sort(sort_by, sort_direction))
        
        # Convert ObjectId to string
        for file in files:
            file['_id'] = str(file['_id'])
        
        return files
    
    def get_by_id(self, file_id: str) -> Optional[Dict]:
        """
        Get a single file by ID
        
        Args:
            file_id: MongoDB ObjectId as string
        
        Returns:
            Dict: File document or None if not found
        """
        try:
            file = self.collection.find_one({'_id': ObjectId(file_id)})
            if file:
                file['_id'] = str(file['_id'])
            return file
        except Exception as e:
            print(f"Error fetching file {file_id}: {str(e)}")
            return None
    
    def delete(self, file_id: str) -> bool:
        """
        Delete a file document from MongoDB
        
        Args:
            file_id: MongoDB ObjectId as string
        
        Returns:
            bool: True if deleted, False otherwise
        """
        try:
            result = self.collection.delete_one({'_id': ObjectId(file_id)})
            return result.deleted_count > 0
        except Exception as e:
            print(f"Error deleting file {file_id}: {str(e)}")
            return False
    
    def update_status(
        self,
        file_id: str,
        status: str,
        log_count: Optional[int] = None
    ) -> bool:
        """
        Update file status and optionally log count
        
        Args:
            file_id: MongoDB ObjectId as string
            status: New status (pending, processing, completed, error)
            log_count: Optional log count to update
        
        Returns:
            bool: True if updated, False otherwise
        """
        try:
            update_data = {
                'status': status,
                'updated_at': datetime.utcnow().isoformat()
            }
            
            if log_count is not None:
                update_data['log_count'] = log_count
            
            result = self.collection.update_one(
                {'_id': ObjectId(file_id)},
                {'$set': update_data}
            )
            
            return result.modified_count > 0
        except Exception as e:
            print(f"Error updating file {file_id}: {str(e)}")
            return False
    
    def get_statistics(self) -> Dict:
        """
        Get file statistics
        
        Returns:
            Dict: Statistics including total files, logs, and size
        """
        try:
            pipeline = [
                {
                    '$group': {
                        '_id': None,
                        'total_files': {'$sum': 1},
                        'total_logs': {'$sum': '$log_count'},
                        'total_size': {'$sum': '$file_size'}
                    }
                }
            ]
            
            result = list(self.collection.aggregate(pipeline))
            
            if result:
                stats = result[0]
                return {
                    'total_files': stats.get('total_files', 0),
                    'total_logs': stats.get('total_logs', 0),
                    'total_size': stats.get('total_size', 0)
                }
            else:
                return {
                    'total_files': 0,
                    'total_logs': 0,
                    'total_size': 0
                }
        except Exception as e:
            print(f"Error getting statistics: {str(e)}")
            return {
                'total_files': 0,
                'total_logs': 0,
                'total_size': 0
            }
    
    def get_by_status(self, status: str) -> List[Dict]:
        """
        Get files by status
        
        Args:
            status: File status to filter by
        
        Returns:
            List[Dict]: List of matching file documents
        """
        files = list(self.collection.find({'status': status}).sort('upload_date', -1))
        
        # Convert ObjectId to string
        for file in files:
            file['_id'] = str(file['_id'])
        
        return files
    
    def count(self) -> int:
        """
        Get total count of files
        
        Returns:
            int: Total number of files
        """
        return self.collection.count_documents({})

# File Management Page

## Overview

The File Management page provides a comprehensive interface for viewing and managing uploaded log files. It displays file statistics, a detailed file list, and allows deletion of files with confirmation.

## Features

### 1. Statistics Dashboard
- **Total Files**: Count of all uploaded files
- **Total Logs Processed**: Sum of all logs across all files
- **Total Size**: Combined size of all files (formatted in B/KB/MB)

### 2. File List Table
Displays all uploaded files with the following information:
- **Filename**: Original file name with file icon
- **Type**: File format badge (CSV or JSON)
- **Size**: File size formatted (B/KB/MB)
- **Upload Date**: Smart date formatting (Today, Yesterday, or full date)
- **Logs**: Number of log entries in the file
- **Status**: Upload status (Success, Processing, Error, Pending)
- **Actions**: Delete button for file removal

### 3. Delete Functionality
- Click delete button on any file
- Confirmation modal appears with file details
- Deletes both physical file and MongoDB record
- Updates statistics automatically
- Shows success notification

## API Endpoints

### GET /files
Renders the file management page.

**Response**: HTML page

### GET /api/files
Retrieves all uploaded files with statistics.

**Response**:
```json
{
  "success": true,
  "files": [
    {
      "_id": "69033334ba0f0d6bb8814d83",
      "filename": "test_upload.csv",
      "saved_as": "20251030_094316_test_upload.csv",
      "file_type": "csv",
      "file_size": 214,
      "upload_date": "2025-10-30T09:43:16.679485",
      "status": "completed",
      "log_count": 3
    }
  ],
  "stats": {
    "total_files": 4,
    "total_logs": 10,
    "total_size": 1068
  }
}
```

### DELETE /api/files/<file_id>
Deletes a specific file.

**Parameters**:
- `file_id`: MongoDB ObjectId of the file to delete

**Response**:
```json
{
  "success": true,
  "message": "File test_upload.json deleted successfully"
}
```

**Actions Performed**:
1. Finds file document in MongoDB
2. Deletes physical file from `/app/uploads/` directory
3. Removes MongoDB document
4. Returns success message

## Usage

### Accessing the Page
Navigate to: `http://localhost:5000/files`

### Viewing Files
- The page automatically loads all files on open
- Statistics update dynamically based on file list
- Click "Refresh" button to reload the list

### Deleting Files
1. Click the red "Delete" button for any file
2. A confirmation modal will appear
3. Review the filename to ensure correct file
4. Click "Delete" to confirm or "Cancel" to abort
5. On success, the file is removed and list refreshes

### Navigation
The page includes navigation links to:
- **Home**: Dashboard with real-time statistics
- **Upload**: Upload new log files
- **Search**: Search and filter logs
- **Files**: Current page (active)

## JavaScript Functions

### Core Functions

**`loadFiles()`**
- Fetches files from API
- Updates statistics
- Populates table
- Shows empty state if no files

**`updateStatistics(stats)`**
- Updates the three statistic cards
- Formats numbers with proper locale

**`displayFiles(files)`**
- Generates table rows
- Applies formatting to each column
- Handles empty state

**`formatFileSize(bytes)`**
- Converts bytes to human-readable format
- Returns: "0 B", "1.04 KB", "2.5 MB"

**`formatDate(dateString)`**
- Smart date formatting:
  - Today: "**Today** at 2:43 PM"
  - Yesterday: "**Yesterday** at 2:43 PM"
  - Older: "Oct 30, 2025\n2:43 PM"

**`formatStatus(status)`**
- Returns colored badge HTML
- Statuses: success (green), processing (yellow), error (red), pending (gray)

**`showDeleteConfirmation(fileId, filename)`**
- Shows Bootstrap modal
- Stores file ID for deletion

**Delete Handler**
- Shows loading overlay
- Sends DELETE request
- Updates list on success
- Shows alert notification

## Styling

### Theme Colors
- **Primary**: Purple gradient (`#667eea` to `#764ba2`)
- **Secondary**: Pink gradient (`#f093fb` to `#f5576c`)
- **Accent**: Blue gradient (`#4facfe` to `#00f2fe`)

### Components
- **Statistics Cards**: Animated hover effect (lift on hover)
- **Table**: Hover highlighting on rows
- **Badges**: Color-coded for file types and statuses
- **Modal**: Standard Bootstrap 5 styling
- **Buttons**: Gradient backgrounds with transitions

## Empty State

When no files are uploaded, the page displays:
- Large inbox icon
- "No Files Uploaded" message
- "Upload your first log file to get started" text
- "Upload Files" button linking to `/upload`

## Error Handling

### API Errors
- Catches fetch errors
- Displays error alerts
- Logs to console for debugging

### Delete Errors
- Shows error message in alert
- Doesn't reload list on failure
- Logs error details

### XSS Prevention
- All user-provided content is escaped
- `escapeHtml()` function used for filenames
- Template literals properly formatted

## Testing

### Manual Testing
1. Access `http://localhost:5000/files`
2. Verify statistics display correctly
3. Check file list populates
4. Test delete functionality
5. Verify empty state when no files exist

### API Testing
```bash
# Get all files
curl http://localhost:5000/api/files

# Delete a file
curl -X DELETE http://localhost:5000/api/files/<file_id>

# Check page loads
curl http://localhost:5000/files
```

## Security Considerations

### Current Implementation
- ⚠️ No authentication/authorization
- ⚠️ No rate limiting on DELETE endpoint
- ⚠️ No audit logging for deletions
- ✓ XSS prevention via HTML escaping
- ✓ MongoDB ObjectId validation

### Recommended Enhancements
1. Add user authentication
2. Implement role-based access control
3. Add audit logging for file deletions
4. Implement rate limiting
5. Add "undo" functionality for deletions
6. Add batch operations (delete multiple files)

## Future Enhancements

### Possible Features
- **Sorting**: Sort table by any column
- **Filtering**: Filter by file type, status, date range
- **Pagination**: For large file lists
- **Bulk Actions**: Delete multiple files at once
- **File Preview**: View file contents before deletion
- **Download**: Re-download uploaded files
- **Search**: Search files by name
- **Details View**: Expand rows to show more metadata
- **Activity Log**: Show file upload/delete history

## Troubleshooting

### Files Don't Load
1. Check MongoDB connection: `docker-compose logs mongodb`
2. Check webapp logs: `docker-compose logs webapp`
3. Verify API response: `curl http://localhost:5000/api/files`
4. Check browser console for JavaScript errors

### Delete Fails
1. Verify file exists in MongoDB
2. Check file exists in `/app/uploads/`
3. Check webapp has write permissions
4. Review webapp logs for errors

### Statistics Wrong
1. Verify `log_count` field in MongoDB documents
2. Check all files have `file_size` field
3. Reload page to refresh data

## Integration

### With Upload Feature
- Files uploaded via `/upload` appear automatically
- Status changes from "processing" to "completed"
- Log count updates after processing

### With Search Feature
- Deleted files' logs remain in Elasticsearch
- Consider adding option to delete logs when deleting file

### With Dashboard
- Consider adding recent files widget to home page
- Link dashboard "total files" stat to files page

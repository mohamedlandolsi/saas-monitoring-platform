# Kibana Setup Guide

Complete step-by-step instructions to create visualizations and dashboards for your SaaS log monitoring platform.

## 📋 Prerequisites

- Elasticsearch running on `http://localhost:9200`
- Kibana running on `http://localhost:5601`
- Log data indexed in `saas-logs-*` indices
- At least 100+ logs generated (run `python generate_logs.py` if needed)

---

## 🎯 Initial Setup

### Step 1: Access Kibana

1. Open your browser and navigate to: **http://localhost:5601**
2. Wait for Kibana to fully load (first startup may take 2-3 minutes)

### Step 2: Create Index Pattern

Before creating visualizations, you need to create an index pattern:

1. Click on **☰ Menu** (hamburger icon) in the top-left
2. Navigate to **Management** → **Stack Management**
3. Click **Index Patterns** under Kibana section
4. Click **Create index pattern** button
5. In "Index pattern name" field, enter: `saas-logs-*`
6. Click **Next step**
7. Select **@timestamp** as the Time field
8. Click **Create index pattern**

✅ You should see confirmation that the index pattern was created successfully.

---

## 📊 Visualization 1: Response Time Line Chart

**Purpose**: Monitor average response times over time to identify performance trends.

### Steps:

1. **Navigate to Visualize**
   - Click **☰ Menu** → **Analytics** → **Visualize Library**
   - Click **Create visualization** button

2. **Select Visualization Type**
   - Choose **Lens** (recommended) or **Line**
   - Select your index pattern: `saas-logs-*`

3. **Configure the Chart**
   - **Y-axis (Vertical)**:
     - Aggregation: `Average`
     - Field: `response_time_ms`
     - Custom label: "Avg Response Time (ms)"
   
   - **X-axis (Horizontal)**:
     - Aggregation: `Date Histogram`
     - Field: `@timestamp`
     - Interval: `Auto` or `1 hour`
     - Custom label: "Time"

4. **Apply Filters** (Optional)
   - Add filter: `status_code` is between `200` and `299` (to see only successful requests)

5. **Customize Appearance**
   - Click **Visual options** or **Options** tab
   - Enable **Smooth lines** for better visualization
   - Set Y-axis label: "Response Time (ms)"
   - Set Chart title: "Average Response Time Over Time"

6. **Save Visualization**
   - Click **Save** button in top-right
   - Title: `Response Time Timeline`
   - Description: "Average API response time over time"
   - Click **Save**

---

## 📊 Visualization 2: Status Code Pie Chart

**Purpose**: View the distribution of HTTP status codes (success vs errors).

### Steps:

1. **Create New Visualization**
   - **☰ Menu** → **Visualize Library** → **Create visualization**

2. **Select Type**
   - Choose **Pie** chart
   - Select index: `saas-logs-*`

3. **Configure Metrics**
   - **Slice size**:
     - Aggregation: `Count`
     - Custom label: "Requests"

4. **Configure Buckets**
   - Click **Add** → **Split slices**
   - Aggregation: `Terms`
   - Field: `status_code`
   - Order by: `Metric: Count`
   - Order: `Descending`
   - Size: `10`
   - Custom label: "Status Code"

5. **Customize Appearance**
   - Click **Options** tab
   - Enable **Donut** mode (optional)
   - Enable **Show labels**
   - Enable **Show values**
   - **Legend position**: Right

6. **Add Color Coding** (Optional)
   - You can manually set colors for common status codes:
     - 200-299: Green
     - 400-499: Yellow/Orange
     - 500-599: Red

7. **Save Visualization**
   - Click **Save**
   - Title: `Status Code Distribution`
   - Description: "HTTP status code breakdown"
   - Click **Save**

---

## 📊 Visualization 3: Top Endpoints Bar Chart

**Purpose**: Identify which API endpoints receive the most traffic.

### Steps:

1. **Create New Visualization**
   - **☰ Menu** → **Visualize Library** → **Create visualization**

2. **Select Type**
   - Choose **Bar** (Vertical Bar) or **Horizontal Bar**
   - Select index: `saas-logs-*`

3. **Configure Y-axis**
   - Aggregation: `Count`
   - Custom label: "Request Count"

4. **Configure X-axis**
   - Click **Add** → **X-axis**
   - Aggregation: `Terms`
   - Field: `endpoint.keyword` (use .keyword for exact match)
   - Order by: `Metric: Count`
   - Order: `Descending`
   - Size: `15` (top 15 endpoints)
   - Custom label: "Endpoint"

5. **Add Split Series** (Optional)
   - To see status codes per endpoint:
   - Click **Add** → **Split series**
   - Sub-aggregation: `Terms`
   - Field: `status_code`
   - Size: `5`

6. **Customize Appearance**
   - **Options** tab:
     - Enable **Show values on chart**
     - Set **Bar orientation**: Vertical or Horizontal
     - Adjust **Label rotation** if needed

7. **Save Visualization**
   - Click **Save**
   - Title: `Top Endpoints by Traffic`
   - Description: "Most frequently accessed API endpoints"
   - Click **Save**

---

## 📊 Visualization 4: Error Rate Timeline

**Purpose**: Monitor error frequency over time to detect issues quickly.

### Steps:

1. **Create New Visualization**
   - **☰ Menu** → **Visualize Library** → **Create visualization**

2. **Select Type**
   - Choose **Area** chart or **Line** chart
   - Select index: `saas-logs-*`

3. **Configure Metrics Panel**
   - Click **Add** → **Y-axis**
   
   - **Metric 1** (Total Errors):
     - Aggregation: `Count`
     - Add filter: `status_code` is greater than or equal to `400`
     - Custom label: "Errors (4xx + 5xx)"
   
   - **Optional Metric 2** (Success Rate):
     - Click **Add metric** → **Y-axis**
     - Aggregation: `Count`
     - Add filter: `status_code` is between `200` and `299`
     - Custom label: "Success (2xx)"

4. **Configure X-axis**
   - Aggregation: `Date Histogram`
   - Field: `@timestamp`
   - Minimum interval: `5 minutes` or `Auto`
   - Custom label: "Time"

5. **Add Split Series** (Optional)
   - To separate 4xx and 5xx errors:
   - Click **Add** → **Split series**
   - Sub-aggregation: `Filters`
   - Filter 1: `status_code >= 400 AND status_code < 500` (Label: "Client Errors (4xx)")
   - Filter 2: `status_code >= 500` (Label: "Server Errors (5xx)")

6. **Customize Appearance**
   - **Options** tab:
     - Mode: `Stacked` or `Normal`
     - Enable **Smooth lines**
     - Color for errors: Red/Orange
     - Enable **Threshold line** (optional)

7. **Save Visualization**
   - Click **Save**
   - Title: `Error Rate Over Time`
   - Description: "HTTP error frequency timeline (4xx & 5xx)"
   - Click **Save**

---

## 📊 Visualization 5: Slowest Queries Table

**Purpose**: Identify the slowest database queries and API endpoints for optimization.

### Steps:

1. **Create New Visualization**
   - **☰ Menu** → **Visualize Library** → **Create visualization**

2. **Select Type**
   - Choose **Data Table**
   - Select index: `saas-logs-*`

3. **Configure Metrics**
   - **Metric Columns**:
   
   - **Column 1**:
     - Aggregation: `Average`
     - Field: `response_time_ms`
     - Custom label: "Avg Response (ms)"
   
   - **Column 2**:
     - Click **Add metric** → **Metric**
     - Aggregation: `Max`
     - Field: `response_time_ms`
     - Custom label: "Max Response (ms)"
   
   - **Column 3**:
     - Click **Add metric** → **Metric**
     - Aggregation: `Count`
     - Custom label: "Total Requests"

4. **Configure Rows (Split Table)**
   - Click **Add** → **Split rows**
   - Aggregation: `Terms`
   - Field: `endpoint.keyword`
   - Order by: `Metric: Average response_time_ms`
   - Order: `Descending`
   - Size: `20`
   - Custom label: "Endpoint"

5. **Add Sub-Bucket** (Optional)
   - To also show SQL queries:
   - Click **Add** → **Split rows**
   - Sub-aggregation: `Terms`
   - Field: `sql_query.keyword`
   - Order by: `Metric: Average query_duration_ms`
   - Order: `Descending`
   - Size: `10`

6. **Add Filters**
   - Add filter to exclude empty responses:
   - `response_time_ms` exists

7. **Customize Table**
   - **Options** tab:
     - Enable **Show partial rows**
     - Enable **Show metrics for every bucket**
     - Per page: `20`

8. **Save Visualization**
   - Click **Save**
   - Title: `Slowest Endpoints and Queries`
   - Description: "Top 20 slowest API endpoints by response time"
   - Click **Save**

---

## 📈 Creating a Dashboard

Now that you have all 5 visualizations, combine them into a dashboard:

### Steps:

1. **Create New Dashboard**
   - **☰ Menu** → **Analytics** → **Dashboard**
   - Click **Create dashboard** button

2. **Add Visualizations**
   - Click **Add from library** button
   - Select all 5 visualizations:
     - ✓ Response Time Timeline
     - ✓ Status Code Distribution
     - ✓ Top Endpoints by Traffic
     - ✓ Error Rate Over Time
     - ✓ Slowest Endpoints and Queries
   - Click **Add** or close the panel

3. **Arrange Dashboard Layout**
   
   **Recommended Layout**:
   ```
   Row 1: [Response Time Timeline - Full Width]
   Row 2: [Status Code Pie Chart (Left)] [Error Rate Timeline (Right)]
   Row 3: [Top Endpoints Bar Chart - Full Width]
   Row 4: [Slowest Queries Table - Full Width]
   ```

4. **Resize Panels**
   - Drag corners to resize each panel
   - Drag panels to reposition them
   - Make timeline charts wider for better visibility
   - Adjust table height to show more rows

5. **Set Time Range**
   - Click **time picker** in top-right
   - Select: `Last 30 days` or `Last 7 days`
   - Or use **Absolute time range** for specific dates

6. **Add Filters** (Optional)
   - Click **Add filter**
   - Example: `log_type: api` to show only API logs
   - Example: `tenant_id: tenant_0001` for specific tenant

7. **Enable Auto-Refresh**
   - Click **Refresh** dropdown near time picker
   - Select refresh interval: `30 seconds`, `1 minute`, etc.

8. **Save Dashboard**
   - Click **Save** button in top-right
   - Title: `SaaS Application Monitoring Dashboard`
   - Description: "Complete overview of API performance, errors, and traffic"
   - Check **Store time with dashboard** (optional)
   - Click **Save**

---

## 🎨 Advanced Customization

### Color Themes

Make visualizations more intuitive with custom colors:

**Status Codes**:
- 2xx (Success): Green `#28a745`
- 3xx (Redirect): Blue `#17a2b8`
- 4xx (Client Error): Orange `#ffc107`
- 5xx (Server Error): Red `#dc3545`

**Log Levels**:
- Info: Blue `#17a2b8`
- Warning: Yellow `#ffc107`
- Error: Red `#dc3545`
- Debug: Gray `#6c757d`

### Adding Threshold Lines

For response time charts:
1. Edit visualization
2. Click **Visual options** → **Reference lines**
3. Add line at `500ms` (warning threshold)
4. Add line at `1000ms` (critical threshold)
5. Set colors: yellow and red respectively

### Adding Data Labels

For better readability:
1. Edit any chart
2. Go to **Options** → **Labels**
3. Enable **Show labels**
4. Enable **Show values**
5. Adjust **Label position** as needed

---

## 🔍 Useful Queries and Filters

### Common Filters

```
# Only errors
status_code >= 400

# Only server errors
status_code >= 500 AND status_code < 600

# Slow requests (over 1 second)
response_time_ms > 1000

# Specific tenant
tenant_id: "tenant_0001"

# Authentication endpoints
endpoint: "/api/auth/*"

# Successful requests only
status_code >= 200 AND status_code < 300
```

### KQL (Kibana Query Language) Examples

```
# Search in messages
message: "error" OR message: "failed"

# Specific user
user_id: "user_00123"

# Exclude health checks
NOT endpoint: "/health"

# Payment-related logs
log_type: "payment" AND status_code: 200
```

---

## 🚀 Next Steps

1. **Set up Alerts**
   - Go to **Stack Management** → **Alerts and Actions**
   - Create alerts for:
     - Error rate > 10% in last 5 minutes
     - Average response time > 1000ms
     - Server errors (5xx) detected

2. **Create More Visualizations**
   - Geographic map of client IPs
   - User activity heatmap
   - Tenant-wise resource usage
   - Database query performance

3. **Export and Share**
   - Export dashboard as PDF for reports
   - Share dashboard URL with team members
   - Create read-only users for stakeholders

4. **Machine Learning** (if X-Pack available)
   - Anomaly detection for response times
   - Forecasting traffic patterns
   - Unusual status code patterns

---

## 📚 Additional Resources

- [Kibana Official Documentation](https://www.elastic.co/guide/en/kibana/8.11/index.html)
- [Kibana Lens Tutorial](https://www.elastic.co/guide/en/kibana/8.11/lens.html)
- [KQL Syntax Guide](https://www.elastic.co/guide/en/kibana/8.11/kuery-query.html)
- [Dashboard Best Practices](https://www.elastic.co/guide/en/kibana/8.11/dashboard.html)

---

## 🛠️ Troubleshooting

### Issue: No data in visualizations
**Solution**: 
- Check if Logstash processed the files: `docker-compose logs logstash`
- Verify index exists: Go to **Dev Tools** and run `GET _cat/indices/saas-logs-*`
- Check time range in Kibana (expand to last 30 days)

### Issue: Fields not available
**Solution**:
- Refresh index pattern: **Management** → **Index Patterns** → `saas-logs-*` → **Refresh** button
- Verify field mapping: Click on field name to see its type

### Issue: Visualization loads slowly
**Solution**:
- Reduce time range (e.g., last 7 days instead of 30)
- Decrease bucket size in Terms aggregations
- Add more specific filters
- Consider using sampling

### Issue: Dashboard not updating
**Solution**:
- Check auto-refresh is enabled
- Click **Refresh** button manually
- Verify Logstash is running: `docker-compose ps logstash`

---

**Dashboard Created**: ✅ SaaS Application Monitoring Dashboard  
**Total Visualizations**: 5  
**Estimated Setup Time**: 30-45 minutes  
**Difficulty Level**: Intermediate  

Enjoy monitoring your SaaS application! 🎉

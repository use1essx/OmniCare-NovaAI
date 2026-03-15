-- ===================================================================
-- Healthcare AI V2 - pgAdmin Dashboard Queries
-- ===================================================================
-- Custom SQL queries for monitoring Healthcare AI system health,
-- performance, and data quality from within pgAdmin
-- ===================================================================

-- ===================================================================
-- 1. SYSTEM OVERVIEW DASHBOARD
-- ===================================================================

-- System Health Overview
SELECT 
    'System Health' as metric_category,
    'Total Users' as metric_name,
    COUNT(*) as value,
    'Active users in the system' as description
FROM users WHERE is_active = true

UNION ALL

SELECT 
    'System Health',
    'Conversations Today',
    COUNT(*),
    'Conversations processed today'
FROM conversations 
WHERE DATE(created_at) = CURRENT_DATE

UNION ALL

SELECT 
    'System Health',
    'HK Data Sources',
    COUNT(DISTINCT source_type),
    'Active HK data sources'
FROM hk_healthcare_data 
WHERE last_updated > NOW() - INTERVAL '24 hours'

UNION ALL

SELECT 
    'System Health',
    'Documents Pending',
    COUNT(*),
    'Documents awaiting approval'
FROM uploaded_documents 
WHERE status = 'pending_approval'

ORDER BY metric_category, metric_name;

-- ===================================================================
-- 2. AGENT PERFORMANCE DASHBOARD
-- ===================================================================

-- Agent Performance Summary
WITH agent_stats AS (
    SELECT 
        agent_type,
        COUNT(*) as total_conversations,
        AVG(agent_confidence) as avg_confidence,
        AVG(user_satisfaction) as avg_satisfaction,
        AVG(processing_time_ms) as avg_processing_time,
        COUNT(CASE WHEN urgency_level = 'emergency' THEN 1 END) as emergency_cases
    FROM conversations 
    WHERE created_at > NOW() - INTERVAL '7 days'
    GROUP BY agent_type
)
SELECT 
    agent_type as "Agent Type",
    total_conversations as "Total Conversations (7 days)",
    ROUND(avg_confidence::numeric, 3) as "Avg Confidence",
    ROUND(avg_satisfaction::numeric, 2) as "Avg User Satisfaction",
    ROUND(avg_processing_time::numeric, 0) as "Avg Processing Time (ms)",
    emergency_cases as "Emergency Cases",
    CASE 
        WHEN avg_satisfaction >= 4.0 THEN '🟢 Excellent'
        WHEN avg_satisfaction >= 3.0 THEN '🟡 Good'
        ELSE '🔴 Needs Improvement'
    END as "Performance Status"
FROM agent_stats
ORDER BY total_conversations DESC;

-- ===================================================================
-- 3. HK DATA INTEGRATION MONITORING
-- ===================================================================

-- HK Data Sources Health Check
WITH data_freshness AS (
    SELECT 
        source_type,
        facility_type,
        COUNT(*) as total_records,
        MAX(last_updated) as last_update,
        EXTRACT(EPOCH FROM (NOW() - MAX(last_updated)))/3600 as hours_since_update,
        AVG(quality_score) as avg_quality_score
    FROM hk_healthcare_data 
    GROUP BY source_type, facility_type
)
SELECT 
    source_type as "Data Source",
    facility_type as "Facility Type",
    total_records as "Total Records",
    last_update as "Last Updated",
    ROUND(hours_since_update::numeric, 1) as "Hours Since Update",
    ROUND(avg_quality_score::numeric, 2) as "Avg Quality Score",
    CASE 
        WHEN hours_since_update < 2 THEN '🟢 Fresh'
        WHEN hours_since_update < 24 THEN '🟡 Moderate'
        ELSE '🔴 Stale'
    END as "Data Status"
FROM data_freshness
ORDER BY hours_since_update ASC;

-- ===================================================================
-- 4. USER ACTIVITY ANALYSIS
-- ===================================================================

-- Daily User Activity Trends
SELECT 
    DATE(created_at) as date,
    COUNT(DISTINCT session_id) as unique_sessions,
    COUNT(*) as total_conversations,
    COUNT(CASE WHEN language = 'zh-HK' THEN 1 END) as chinese_conversations,
    COUNT(CASE WHEN language = 'en' THEN 1 END) as english_conversations,
    ROUND(AVG(user_satisfaction)::numeric, 2) as avg_satisfaction,
    COUNT(CASE WHEN urgency_level = 'emergency' THEN 1 END) as emergency_cases
FROM conversations 
WHERE created_at > NOW() - INTERVAL '30 days'
GROUP BY DATE(created_at)
ORDER BY date DESC
LIMIT 30;

-- ===================================================================
-- 5. SECURITY MONITORING
-- ===================================================================

-- Security Events Overview
SELECT 
    event_type as "Event Type",
    COUNT(*) as "Count (24h)",
    MAX(created_at) as "Last Occurrence",
    COUNT(DISTINCT user_id) as "Unique Users Affected",
    CASE 
        WHEN event_type IN ('login_failure', 'account_locked') THEN '🔴 High Priority'
        WHEN event_type IN ('password_change', 'role_change') THEN '🟡 Medium Priority'
        ELSE '🟢 Low Priority'
    END as "Priority Level"
FROM audit_logs 
WHERE created_at > NOW() - INTERVAL '24 hours'
GROUP BY event_type
ORDER BY COUNT(*) DESC;

-- Failed Login Attempts by IP
SELECT 
    ip_address as "IP Address",
    COUNT(*) as "Failed Attempts",
    MAX(created_at) as "Last Attempt",
    COUNT(DISTINCT user_email) as "Different Users Targeted",
    CASE 
        WHEN COUNT(*) > 10 THEN '🔴 Potential Attack'
        WHEN COUNT(*) > 5 THEN '🟡 Suspicious'
        ELSE '🟢 Normal'
    END as "Threat Level"
FROM audit_logs 
WHERE event_type = 'login_failure' 
AND created_at > NOW() - INTERVAL '24 hours'
GROUP BY ip_address
HAVING COUNT(*) > 3
ORDER BY COUNT(*) DESC;

-- ===================================================================
-- 6. PERFORMANCE MONITORING
-- ===================================================================

-- Database Performance Overview
SELECT 
    schemaname as "Schema",
    tablename as "Table",
    n_tup_ins as "Inserts",
    n_tup_upd as "Updates", 
    n_tup_del as "Deletes",
    n_live_tup as "Live Tuples",
    n_dead_tup as "Dead Tuples",
    CASE 
        WHEN n_dead_tup > n_live_tup * 0.1 THEN '🔴 Needs VACUUM'
        WHEN n_dead_tup > n_live_tup * 0.05 THEN '🟡 Consider VACUUM'
        ELSE '🟢 Good'
    END as "Table Health"
FROM pg_stat_user_tables 
WHERE schemaname = 'public'
ORDER BY n_live_tup DESC;

-- Query Performance (requires pg_stat_statements extension)
SELECT 
    query as "Query Pattern",
    calls as "Execution Count",
    ROUND((total_exec_time / calls)::numeric, 2) as "Avg Time (ms)",
    ROUND((100.0 * total_exec_time / sum(total_exec_time) OVER())::numeric, 2) as "% of Total Time",
    CASE 
        WHEN (total_exec_time / calls) > 1000 THEN '🔴 Slow'
        WHEN (total_exec_time / calls) > 500 THEN '🟡 Moderate'
        ELSE '🟢 Fast'
    END as "Performance"
FROM pg_stat_statements 
WHERE query NOT LIKE '%pg_stat_statements%'
ORDER BY total_exec_time DESC 
LIMIT 20;

-- ===================================================================
-- 7. DATA QUALITY MONITORING
-- ===================================================================

-- Data Quality Report
WITH quality_check AS (
    SELECT 
        'Conversations' as table_name,
        COUNT(*) as total_records,
        COUNT(CASE WHEN user_input IS NULL OR user_input = '' THEN 1 END) as missing_user_input,
        COUNT(CASE WHEN agent_response IS NULL OR agent_response = '' THEN 1 END) as missing_agent_response,
        COUNT(CASE WHEN agent_confidence < 0.5 THEN 1 END) as low_confidence_responses
    FROM conversations
    
    UNION ALL
    
    SELECT 
        'HK Healthcare Data',
        COUNT(*),
        COUNT(CASE WHEN name_en IS NULL AND name_zh IS NULL THEN 1 END),
        COUNT(CASE WHEN address IS NULL OR address = '' THEN 1 END),
        COUNT(CASE WHEN quality_score < 0.7 THEN 1 END)
    FROM hk_healthcare_data
    
    UNION ALL
    
    SELECT 
        'Uploaded Documents',
        COUNT(*),
        COUNT(CASE WHEN content IS NULL OR content = '' THEN 1 END),
        COUNT(CASE WHEN category IS NULL THEN 1 END),
        COUNT(CASE WHEN quality_score < 0.6 THEN 1 END)
    FROM uploaded_documents
)
SELECT 
    table_name as "Table",
    total_records as "Total Records",
    missing_user_input as "Data Issues",
    missing_agent_response as "Missing Critical Data",
    low_confidence_responses as "Quality Concerns",
    ROUND(((total_records - missing_user_input - missing_agent_response) * 100.0 / total_records)::numeric, 1) as "Data Quality %"
FROM quality_check
ORDER BY total_records DESC;

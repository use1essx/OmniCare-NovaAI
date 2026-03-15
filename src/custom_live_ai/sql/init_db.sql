-- Custom Live AI - Database Initialization Script
-- Auto-run on first PostgreSQL container startup

-- Create database (if not exists - handled by POSTGRES_DB env var)
-- This script runs AFTER database is created

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create users table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    age INTEGER,
    gender VARCHAR(50),
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create index on user_id for faster lookups
CREATE INDEX IF NOT EXISTS idx_users_user_id ON users(user_id);

-- Create sessions table
CREATE TABLE IF NOT EXISTS sessions (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) UNIQUE NOT NULL,
    user_id VARCHAR(100) REFERENCES users(user_id) ON DELETE CASCADE,
    
    -- Session timing
    start_time TIMESTAMP WITH TIME ZONE,
    end_time TIMESTAMP WITH TIME ZONE,
    duration FLOAT,
    
    -- Recording quality
    total_frames INTEGER,
    avg_fps FLOAT,
    recording_quality VARCHAR(50),
    
    -- File paths
    json_file VARCHAR(500),
    csv_file VARCHAR(500),
    
    -- Detection rates
    face_detection_rate FLOAT,
    
    -- Average emotion metrics
    avg_smile_score FLOAT,
    avg_eye_open_left FLOAT,
    avg_eye_open_right FLOAT,
    avg_eyebrow_height FLOAT,
    avg_mouth_open FLOAT,
    
    -- Behavioral insights
    blinks_detected INTEGER,
    smile_frames INTEGER,
    surprise_moments INTEGER,
    
    -- Real-time tracking metrics (NEW)
    intervention_count INTEGER DEFAULT 0,
    avg_response_time FLOAT,  -- Average time to respond to interventions
    emotion_variance FLOAT,  -- Variance in emotion scores (stability measure)
    posture_improvement_score FLOAT,  -- How much posture improved during session
    
    -- Additional data
    session_metadata JSONB,
    notes TEXT,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for sessions
CREATE INDEX IF NOT EXISTS idx_sessions_session_id ON sessions(session_id);
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_created_at ON sessions(created_at);

-- Create emotion_events table (optional, for detailed tracking)
CREATE TABLE IF NOT EXISTS emotion_events (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) REFERENCES sessions(session_id) ON DELETE CASCADE,
    
    -- Event details
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    frame_number INTEGER NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    intensity FLOAT,
    duration FLOAT,
    
    -- Additional event data
    data JSONB,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for emotion_events
CREATE INDEX IF NOT EXISTS idx_emotion_events_session_id ON emotion_events(session_id);
CREATE INDEX IF NOT EXISTS idx_emotion_events_timestamp ON emotion_events(timestamp);

-- Create intervention_logs table for real-time AI interventions
CREATE TABLE IF NOT EXISTS intervention_logs (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) REFERENCES sessions(session_id) ON DELETE CASCADE,
    
    -- Intervention details
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    intervention_type VARCHAR(100) NOT NULL,  -- posture_reminder, emotion_support, break_suggestion, etc.
    trigger_reason VARCHAR(255),  -- poor_posture_5min, negative_emotion_3min, etc.
    message_sent TEXT,
    tone_used VARCHAR(50),  -- formal, friendly, encouraging, gentle, calm, etc.
    user_response VARCHAR(100),  -- Optional: acknowledged, ignored, improved, etc.
    effectiveness_score FLOAT,  -- Optional: 0.0-1.0 for future ML
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for intervention_logs
CREATE INDEX IF NOT EXISTS idx_intervention_logs_session_id ON intervention_logs(session_id);
CREATE INDEX IF NOT EXISTS idx_intervention_logs_timestamp ON intervention_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_intervention_logs_type ON intervention_logs(intervention_type);

-- Create a function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for users table
DROP TRIGGER IF EXISTS update_users_updated_at ON users;
CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Insert a test user (optional - for testing)
INSERT INTO users (user_id, name, age, gender, notes)
VALUES ('test_user_001', 'Test User', 25, 'male', 'Auto-created test user for development')
ON CONFLICT (user_id) DO NOTHING;

-- Success message
DO $$
BEGIN
    RAISE NOTICE '✅ Custom Live AI database initialized successfully!';
    RAISE NOTICE '📊 Tables created: users, sessions, emotion_events';
    RAISE NOTICE '👤 Test user created: test_user_001';
END $$;



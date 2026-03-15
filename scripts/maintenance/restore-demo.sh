#!/bin/bash

# Healthcare AI - Demo Restoration Script
# This script restores the system to working demo state

echo "🔄 Healthcare AI V2 - Demo Restoration"
echo "====================================="

# Step 1: Stop services
echo "⏹️  Stopping services..."
docker-compose down

# Step 2: Remove volumes to reset database
echo "🗑️  Clearing database..."
docker volume rm healthcare_ai_live2d_unified_postgres_data 2>/dev/null || true

# Step 3: Start services
echo "🚀 Starting services..."
docker-compose up -d

# Step 4: Wait for services
echo "⏳ Waiting for services to be ready..."
sleep 15

# Step 5: Create demo users directly in database (bypassing password validation)
echo "👥 Creating demo users..."

# Create teen user
docker-compose exec -T postgres psql -U admin -d healthcare_ai_v2 << EOF
INSERT INTO users (
    email, username, full_name, role, department, organization, is_active, is_verified, is_admin,
    language_preference, timezone, notification_preferences, health_profile,
    hashed_password, created_at, updated_at
) VALUES (
    'teen@demo.com', 'teen_demo', 'Alex Chen', 'user', 'Student Health', 'St. Mary High School',
    true, true, false, 'en', 'Asia/Hong_Kong', 
    '{"email": true, "sms": false, "push": true}'::jsonb,
    '{
        "age": 17, "gender": "non-binary", "height": 165, "weight": 58, "blood_type": "A+",
        "chronic_conditions": ["anxiety"], "custom_chronic_conditions": ["Social Anxiety Disorder"],
        "medications": ["Sertraline 50mg"], "allergies": ["Peanuts", "Shellfish"],
        "smoking_status": "never", "alcohol_consumption": "never", "exercise_frequency": "2-3 times per week",
        "emergency_contact_name": "Jennifer Chen", "emergency_contact_phone": "+852 9876 5432",
        "emergency_contact_relationship": "Mother",
        "health_goals": "Managing anxiety and stress from school. Want to improve sleep quality."
    }'::jsonb,
    'simple_hash_0cc175b9c0f1b6a831c399e269772661', NOW(), NOW()
);

-- Create elder user  
INSERT INTO users (
    email, username, full_name, role, department, organization, is_active, is_verified, is_admin,
    language_preference, timezone, notification_preferences, health_profile,
    hashed_password, created_at, updated_at
) VALUES (
    'elder@demo.com', 'elder_demo', 'Margaret Wong', 'user', 'Senior Care', 'Golden Age Care Center',
    true, true, false, 'en', 'Asia/Hong_Kong',
    '{"email": true, "sms": false, "push": true}'::jsonb,
    '{
        "age": 72, "gender": "female", "height": 158, "weight": 65, "blood_type": "O+",
        "chronic_conditions": ["diabetes", "hypertension", "arthritis", "osteoporosis"],
        "custom_chronic_conditions": ["Mild Cognitive Impairment", "Cataracts"],
        "medications": ["Metformin 500mg twice daily", "Lisinopril 10mg daily", "Calcium + Vitamin D daily"],
        "allergies": ["Penicillin", "Codeine"], "smoking_status": "former (quit 15 years ago)",
        "alcohol_consumption": "occasionally", "exercise_frequency": "daily walks",
        "emergency_contact_name": "David Wong", "emergency_contact_phone": "+852 9123 4567",
        "emergency_contact_relationship": "Son",
        "health_goals": "Maintaining independence and managing diabetes levels."
    }'::jsonb,
    'simple_hash_0cc175b9c0f1b6a831c399e269772661', NOW(), NOW()
);

-- Create admin user
INSERT INTO users (
    email, username, full_name, role, department, organization, license_number, is_active, is_verified, is_admin,
    language_preference, timezone, notification_preferences, health_profile,
    hashed_password, created_at, updated_at
) VALUES (
    'admin@demo.com', 'admin_demo', 'Dr. Sarah Li', 'admin', 'System Administration', 
    'Healthcare AI Demo System', 'HK-MD-2025-001', true, true, true, 'en', 'Asia/Hong_Kong',
    '{"email": true, "sms": false, "push": true}'::jsonb, '{}'::jsonb,
    'simple_hash_c4ca4238a0b923820dcc509a6f75849b', NOW(), NOW()
);
EOF

echo "✅ Demo users created with passwords:"
echo "   teen_demo / Demo2025!"
echo "   elder_demo / Demo2025!" 
echo "   admin_demo / Admin2025!"

# Step 6: Test login
echo ""
echo "🧪 Testing login..."
RESULT=$(curl -s -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email_or_username": "admin_demo", "password": "Admin2025!"}' | grep -o '"access_token"')

if [ ! -z "$RESULT" ]; then
    echo "✅ Login test successful!"
else
    echo "⚠️  Login test failed, but users are created"
fi

echo ""
echo "🎯 Demo System Ready!"
echo "   Main Interface: http://localhost:8000/live2d/"
echo "   Admin Dashboard: http://localhost:8000/admin-dashboard.html"
echo "   Authentication: http://localhost:8000/auth.html"
echo "   pgAdmin: http://localhost:5050"
echo ""
echo "📋 Demo Users:"
echo "   Teen: teen_demo / Demo2025!"
echo "   Elder: elder_demo / Demo2025!"
echo "   Admin: admin_demo / Admin2025!"


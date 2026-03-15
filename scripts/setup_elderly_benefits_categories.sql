-- Setup Elderly Benefits Category Structure
-- Creates the proper category hierarchy for elderly benefits

-- Step 1: Create Level 2 category "長者福利" (Elderly Benefits)
INSERT INTO kb_categories 
(name_en, name_zh, slug, icon, description_en, description_zh, level, display_order, parent_id)
SELECT 
    'Elderly Benefits', 
    '長者福利', 
    'elderly-benefits', 
    '💰', 
    'Government benefits and services for elderly citizens',
    '政府為長者提供的福利及服務',
    2, 
    1, 
    id
FROM kb_categories 
WHERE slug = 'elderly' AND level = 1
ON CONFLICT DO NOTHING;

-- Step 2: Create Level 3 topics under "長者福利"
WITH benefits_cat AS (
    SELECT id FROM kb_categories WHERE slug = 'elderly-benefits' AND level = 2
)
INSERT INTO kb_categories 
(name_en, name_zh, slug, icon, description_en, description_zh, level, display_order, parent_id)
SELECT * FROM (VALUES
    ('Elderly Octopus Card', '樂悠咭', 'elderly-octopus-card', '🚇', 
     'Concessionary travel scheme for elderly', '長者交通優惠計劃', 3, 1, (SELECT id FROM benefits_cat)),
    
    ('CSSA', '綜援', 'cssa', '💵', 
     'Comprehensive Social Security Assistance', '綜合社會保障援助計劃', 3, 2, (SELECT id FROM benefits_cat)),
    
    ('Medical Fee Waiver', '醫療費用減免', 'medical-fee-waiver', '🏥', 
     'Medical fee waiver for elderly', '長者醫療費用減免', 3, 3, (SELECT id FROM benefits_cat)),
    
    ('Elderly Dental Assistance', '長者牙科服務資助', 'elderly-dental-assistance', '🦷', 
     'Dental care subsidy for elderly', '長者牙科服務資助計劃', 3, 4, (SELECT id FROM benefits_cat)),
    
    ('Community Care Service Voucher', '長者社區照顧服務券計劃', 'community-care-voucher', '🏘️', 
     'Community care service voucher scheme', '長者社區照顧服務券計劃', 3, 5, (SELECT id FROM benefits_cat)),
    
    ('Elderly Health Care Voucher', '長者醫療券計劃', 'elderly-health-voucher', '💊', 
     'Health care voucher scheme for elderly', '長者醫療券計劃', 3, 6, (SELECT id FROM benefits_cat)),
    
    ('Residential Care Service Voucher', '長者院舍照顧服務券計劃', 'residential-care-voucher', '🏠', 
     'Residential care service voucher scheme', '長者院舍照顧服務券計劃', 3, 7, (SELECT id FROM benefits_cat)),
    
    ('Old Age Allowance', '高齡津貼、傷殘津貼及長者生活津貼', 'old-age-allowance', '💰', 
     'Old age allowance, disability allowance and old age living allowance', 
     '高齡津貼、傷殘津貼及長者生活津貼', 3, 8, (SELECT id FROM benefits_cat))
) AS t(name_en, name_zh, slug, icon, description_en, description_zh, level, display_order, parent_id)
ON CONFLICT DO NOTHING;

-- Show the created structure
SELECT 
    CASE 
        WHEN level = 1 THEN name_zh
        WHEN level = 2 THEN '  └─ ' || name_zh
        WHEN level = 3 THEN '      └─ ' || name_zh
    END as structure,
    id,
    level
FROM kb_categories
WHERE id IN (
    SELECT id FROM kb_categories WHERE slug = 'elderly'
    UNION
    SELECT id FROM kb_categories WHERE slug = 'elderly-benefits'
    UNION
    SELECT id FROM kb_categories WHERE parent_id = (SELECT id FROM kb_categories WHERE slug = 'elderly-benefits')
)
ORDER BY level, display_order;

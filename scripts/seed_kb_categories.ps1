# Seed KB Categories - PowerShell Script
# Handles UTF-8 encoding properly on Windows

Write-Host "🌱 Seeding KB Categories..." -ForegroundColor Green
Write-Host ""

# Root categories
$rootCategories = @(
    @{name_en='Elderly Services'; name_zh='長者服務'; slug='elderly-services'; icon='👴'; desc_en='Government services and benefits for elderly citizens'; desc_zh='政府為長者提供的服務和福利'},
    @{name_en='Children Services'; name_zh='兒童服務'; slug='children-services'; icon='👶'; desc_en='Government services and benefits for children'; desc_zh='政府為兒童提供的服務和福利'},
    @{name_en='Youth Services'; name_zh='青少年服務'; slug='youth-services'; icon='🧑'; desc_en='Government services and benefits for youth'; desc_zh='政府為青少年提供的服務和福利'}
)

# Insert root categories
foreach ($cat in $rootCategories) {
    $sql = "INSERT INTO kb_categories (name_en, name_zh, slug, icon, description_en, description_zh, level, display_order, parent_id) VALUES ('$($cat.name_en)', '$($cat.name_zh)', '$($cat.slug)', '$($cat.icon)', '$($cat.desc_en)', '$($cat.desc_zh)', 0, $($rootCategories.IndexOf($cat) + 1), NULL) ON CONFLICT (slug) DO NOTHING RETURNING id;"
    
    docker exec -i healthcare_ai_postgres psql -U admin -d healthcare_ai_v2 -c $sql | Out-Null
    Write-Host "✅ Created: $($cat.icon) $($cat.name_zh)" -ForegroundColor Green
}

Write-Host ""

# Elderly services sub-categories
$elderlyCategories = @(
    @{name_en='Medical Vouchers'; name_zh='長者醫療券計劃'; slug='medical-vouchers'; icon='🏥'; desc_zh='睇醫生資助'},
    @{name_en='CSSA'; name_zh='綜援'; slug='cssa'; icon='💰'; desc_zh='綜合社會保障援助計劃'},
    @{name_en='Elder Card'; name_zh='樂悠咭'; slug='elder-card'; icon='🚌'; desc_zh='$2交通優惠'},
    @{name_en='Elderly Dental Services'; name_zh='長者牙科服務資助'; slug='elderly-dental'; icon='🦷'; desc_zh='牙科服務資助'},
    @{name_en='Community Care Service Voucher'; name_zh='長者社區照顧服務券計劃'; slug='community-care-voucher'; icon='🏘️'; desc_zh='社區照顧服務券'},
    @{name_en='Residential Care Service Voucher'; name_zh='長者院舍照顧服務券計劃'; slug='residential-care-voucher'; icon='🏠'; desc_zh='院舍照顧服務券'},
    @{name_en='Old Age Allowance'; name_zh='高齡津貼、傷殘津貼及長者生活津貼'; slug='old-age-allowance'; icon='💵'; desc_zh='高齡津貼和傷殘津貼'},
    @{name_en='Medical Fee Waiver'; name_zh='醫療費用減免'; slug='medical-fee-waiver'; icon='🏥'; desc_zh='醫療費用減免'}
)

foreach ($cat in $elderlyCategories) {
    $sql = "INSERT INTO kb_categories (name_en, name_zh, slug, icon, description_zh, level, display_order, parent_id) VALUES ('$($cat.name_en)', '$($cat.name_zh)', '$($cat.slug)', '$($cat.icon)', '$($cat.desc_zh)', 1, $($elderlyCategories.IndexOf($cat) + 1), (SELECT id FROM kb_categories WHERE slug = 'elderly-services')) ON CONFLICT (slug) DO NOTHING;"
    
    docker exec -i healthcare_ai_postgres psql -U admin -d healthcare_ai_v2 -c $sql | Out-Null
    Write-Host "  ✅ Created: $($cat.icon) $($cat.name_zh)" -ForegroundColor Cyan
}

Write-Host ""

# Children services sub-categories
$childrenCategories = @(
    @{name_en='Vaccination'; name_zh='疫苗接種'; slug='vaccination'; icon='💉'; desc_zh='兒童疫苗接種計劃'},
    @{name_en='Preschool Education'; name_zh='學前教育'; slug='preschool'; icon='🎓'; desc_zh='學前教育服務'},
    @{name_en='Child Development'; name_zh='兒童發展'; slug='child-development'; icon='🧸'; desc_zh='兒童發展評估和支援'}
)

foreach ($cat in $childrenCategories) {
    $sql = "INSERT INTO kb_categories (name_en, name_zh, slug, icon, description_zh, level, display_order, parent_id) VALUES ('$($cat.name_en)', '$($cat.name_zh)', '$($cat.slug)', '$($cat.icon)', '$($cat.desc_zh)', 1, $($childrenCategories.IndexOf($cat) + 1), (SELECT id FROM kb_categories WHERE slug = 'children-services')) ON CONFLICT (slug) DO NOTHING;"
    
    docker exec -i healthcare_ai_postgres psql -U admin -d healthcare_ai_v2 -c $sql | Out-Null
    Write-Host "  ✅ Created: $($cat.icon) $($cat.name_zh)" -ForegroundColor Cyan
}

Write-Host ""

# Youth services sub-categories
$youthCategories = @(
    @{name_en='Education Guidance'; name_zh='升學輔導'; slug='education-guidance'; icon='📚'; desc_zh='升學及就業輔導'},
    @{name_en='Employment Support'; name_zh='就業支援'; slug='employment-support'; icon='💼'; desc_zh='青少年就業支援計劃'},
    @{name_en='Mental Health'; name_zh='心理健康'; slug='mental-health'; icon='🧠'; desc_zh='青少年心理健康支援'}
)

foreach ($cat in $youthCategories) {
    $sql = "INSERT INTO kb_categories (name_en, name_zh, slug, icon, description_zh, level, display_order, parent_id) VALUES ('$($cat.name_en)', '$($cat.name_zh)', '$($cat.slug)', '$($cat.icon)', '$($cat.desc_zh)', 1, $($youthCategories.IndexOf($cat) + 1), (SELECT id FROM kb_categories WHERE slug = 'youth-services')) ON CONFLICT (slug) DO NOTHING;"
    
    docker exec -i healthcare_ai_postgres psql -U admin -d healthcare_ai_v2 -c $sql | Out-Null
    Write-Host "  ✅ Created: $($cat.icon) $($cat.name_zh)" -ForegroundColor Cyan
}

Write-Host ""
Write-Host "🎉 Successfully seeded KB categories!" -ForegroundColor Green
Write-Host ""

# Display category tree
Write-Host "📊 Category Tree:" -ForegroundColor Yellow
docker exec -i healthcare_ai_postgres psql -U admin -d healthcare_ai_v2 -c "SELECT name_zh, icon, level FROM kb_categories ORDER BY level, display_order;"

Write-Host ""
Write-Host "Total categories:" -ForegroundColor Yellow
docker exec -i healthcare_ai_postgres psql -U admin -d healthcare_ai_v2 -c "SELECT COUNT(*) as total FROM kb_categories;"

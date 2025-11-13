$filePath = "c:\Users\user\Desktop\BrainInk-Backend\users_micro\Endpoints\study_area.py"
$content = Get-Content $filePath -Raw

# Replace principal role checks
$content = $content -replace 'user = db\.query\(User\)\.filter\(User\.id == current_user\["user_id"\]\)\.first\(\)\s*if not user or user\.role\.name != UserRole\.principal:\s*raise HTTPException\(status_code=403, detail="[^"]*"\)', 'ensure_user_role(db, current_user["user_id"], UserRole.principal)'

# Replace admin role checks  
$content = $content -replace 'admin_user = db\.query\(User\)\.filter\(User\.id == current_user\["user_id"\]\)\.first\(\)\s*if not admin_user or admin_user\.role\.name != UserRole\.admin:\s*raise HTTPException\(status_code=403, detail="[^"]*"\)', 'ensure_user_role(db, current_user["user_id"], UserRole.admin)'

# Replace other admin checks
$content = $content -replace 'user = db\.query\(User\)\.filter\(User\.id == current_user\["user_id"\]\)\.first\(\)\s*if not user or user\.role\.name != UserRole\.admin:\s*raise HTTPException\(status_code=403, detail="[^"]*"\)', 'ensure_user_role(db, current_user["user_id"], UserRole.admin)'

Set-Content $filePath $content -NoNewline

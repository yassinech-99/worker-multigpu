# PowerShell script to encode images to base64 and update the JSON file
param(
    [Parameter(Mandatory=$true)]
    [string]$JsonPath,
    
    [Parameter(Mandatory=$true)]
    [string]$ImagePaths
)

# Function to convert image to base64
function Convert-ImageToBase64 {
    param([string]$ImagePath)
    
    if (Test-Path $ImagePath) {
        $bytes = [System.IO.File]::ReadAllBytes($ImagePath)
        $base64 = [System.Convert]::ToBase64String($bytes)
        return $base64
    } else {
        Write-Error "Image file not found: $ImagePath"
        return $null
    }
}

Write-Host "Converting images to base64..."

# Split the comma-separated image paths into an array
$imagePathArray = $ImagePaths -split ',' | ForEach-Object { $_.Trim() }

# Convert all images to base64
$base64Images = @()
foreach ($imagePath in $imagePathArray) {
    $base64 = Convert-ImageToBase64 -ImagePath $imagePath
    if ($base64) {
        $fileName = [System.IO.Path]::GetFileName($imagePath)
        $base64Images += @{
            name = $fileName
            image = $base64
        }
        Write-Host "Converted: $fileName"
    }
}

if ($base64Images.Count -gt 0) {
    # Read the JSON file
    $jsonContent = Get-Content $JsonPath -Raw | ConvertFrom-Json
    
    # Update the images array
    $jsonContent.input.images = $base64Images
    
    # Save the updated JSON (preserving original formatting)
    $jsonContent | ConvertTo-Json -Depth 20 | Set-Content $JsonPath
    
    Write-Host "Successfully updated $JsonPath with $($base64Images.Count) base64 encoded images"
    
    Write-Host "File size:" -NoNewline
    $fileInfo = Get-Item $JsonPath
    Write-Host " $([math]::Round($fileInfo.Length / 1MB, 2)) MB"
} else {
    Write-Error "No images were successfully converted"
}

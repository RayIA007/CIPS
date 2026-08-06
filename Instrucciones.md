tree /F /A > ESTRUCTURA_PROYECTO.txt

#################################
inventario detallado
#################################
Get-ChildItem -Recurse |
Select-Object `
    FullName,
    DirectoryName,
    Name,
    Extension,
    Length,
    LastWriteTime |
Export-Csv INVENTARIO_PROYECTO.csv -NoTypeInformation -Encoding UTF8

##############################
Detectar nombres de archivo repetidos
##############################
Get-ChildItem -Recurse -File |
Group-Object Name |
Where-Object {$_.Count -gt 1} |
ForEach-Object {
    "ARCHIVO REPETIDO: $($_.Name)"
    $_.Group.FullName
    ""
} |
Set-Content duplicate_file_names.txt -Encoding UTF8

################################
PROJECT_MANIFEST.json
################################
{
  "version": "0.5",
  "modules": 214,
  "packages": 32,
  "providers": [
    "OpenAI",
    "Gemini",
    "Claude",
    "Ollama"
  ],
  "pipelines": [
    "Research",
    "Storyboard",
    "Script",
    "Publication"
  ],
  "knowledge_modules": 186
}

#################################
Detectar archivos realmente idénticos
#################################
Get-ChildItem -Recurse -File |
Where-Object {
    $_.FullName -notmatch '\\.git\\|\\__pycache__\\|\\.venv\\|\\venv\\|\\node_modules\\'
} |
ForEach-Object {
    try {
        [PSCustomObject]@{
            Ruta   = $_.FullName
            Nombre = $_.Name
            Tamaño = $_.Length
            SHA256 = (Get-FileHash $_.FullName -Algorithm SHA256).Hash
        }
    }
    catch {}
} |
Group-Object SHA256 |
Where-Object {$_.Count -gt 1} |
ForEach-Object {
    "GRUPO DE ARCHIVOS IDÉNTICOS"
    "SHA256: $($_.Name)"
    $_.Group | ForEach-Object {"$($_.Ruta)"}
    ""
} |
Set-Content duplicate_file_hashes.txt -Encoding UTF8

###########################################
Obtener detalles internos de todos los archivos Python
##########################################
Get-ChildItem -Recurse -Filter *.py |
Where-Object {
    $_.FullName -notmatch '\\.git\\|\\__pycache__\\|\\.venv\\|\\venv\\'
} |
ForEach-Object {

    $file = $_

    $classes = Get-Content $file.FullName |
        Select-String '^\s*class\s+([A-Za-z_][A-Za-z0-9_]*)' |
        ForEach-Object {$_.Matches.Groups[1].Value}

    $functions = Get-Content $file.FullName |
        Select-String '^\s*(?:async\s+)?def\s+([A-Za-z_][A-Za-z0-9_]*)' |
        ForEach-Object {$_.Matches.Groups[1].Value}

    [PSCustomObject]@{
        RutaRelativa = $file.FullName.Replace((Get-Location).Path + "\", "")
        Archivo       = $file.Name
        TamañoBytes   = $file.Length
        Modificado    = $file.LastWriteTime
        Clases        = ($classes -join "; ")
        Funciones     = ($functions -join "; ")
    }
} |
Export-Csv python_modules_inventory.csv -NoTypeInformation -Encoding UTF8

########################################
Localizar específicamente todos los archivos relacionados con conocimiento
########################################
Get-ChildItem -Recurse -File |
Where-Object {
    $_.Name -match 'knowledge|context|prompt|resolver|injector'
} |
Select-Object FullName, Name, Length, LastWriteTime |
Format-Table -AutoSize |
Out-File knowledge_related_files.txt -Encoding UTF8





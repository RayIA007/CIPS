#!/usr/bin/env python3
"""
CIPS Secret Auditor - Script multiplataforma para auditar secrets en repositorios.
Ejecutar: python cips_secret_auditor.py
"""

import os
import re
import subprocess
import sys
from pathlib import Path

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN
# ═══════════════════════════════════════════════════════════════════════════════

# Extensiones a escanear
EXTENSIONS = {'.py', '.js', '.ts', '.json', '.yaml', '.yml', '.sh', '.md', '.txt', 
              '.cfg', '.ini', '.toml', '.sql', '.html', '.css', '.scss', '.jsx', '.tsx'}

# Directorios a excluir
EXCLUDE_DIRS = {'node_modules', '.git', 'venv', '__pycache__', '.pytest_cache', 
                '.mypy_cache', '.tox', 'dist', 'build', '.next', '.vscode', '.idea',
                'site-packages', 'Lib', 'Scripts', 'Include'}

# Patrones de secrets (regex)
SECRET_PATTERNS = {
    'OpenAI API Key': r'sk-[a-zA-Z0-9]{48,}',
    'AWS Access Key ID': r'AKIA[0-9A-Z]{16}',
    'AWS Secret Access Key': r'[0-9a-zA-Z/+]{40}',
    'GitHub PAT': r'ghp_[a-zA-Z0-9]{36,}',
    'GitHub OAuth': r'gho_[a-zA-Z0-9]{36,}',
    'Slack Token': r'xox[baprs]-[0-9]{10,13}-[0-9]{10,13}(-[a-zA-Z0-9]{24})?',
    'Generic API Key': r'(?i)(api[_-]?key|apikey)\s*[:=]\s*["']?[a-zA-Z0-9_\-]{16,}["']?',
    'Generic Secret': r'(?i)(secret[_-]?key|secretkey|client_secret)\s*[:=]\s*["']?[a-zA-Z0-9_\-]{16,}["']?',
    'Generic Token': r'(?i)(access[_-]?token|auth[_-]?token|bearer)\s*[:=]\s*["']?[a-zA-Z0-9_\-]{16,}["']?',
    'Password in code': r'(?i)(password|passwd|pwd)\s*[:=]\s*["'][^"']{4,}["']',
    'Private Key': r'-----BEGIN (RSA |DSA |EC |OPENSSH )?PRIVATE KEY-----',
    'Connection String': r'(?i)(mongodb(\+srv)?://|postgres(ql)?://|mysql://|redis://|amqp://)[^\s"']+',
    'JWT Token': r'eyJ[a-zA-Z0-9_-]*\.eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*',
    'Google API Key': r'AIza[0-9A-Za-z_-]{35}',
    'Stripe Key': r'sk_(live|test)_[0-9a-zA-Z]{24,}',
    'Twilio SID': r'AC[a-zA-Z0-9]{32}',
    'SendGrid Key': r'SG\.[a-zA-Z0-9_-]{22}\.[a-zA-Z0-9_-]{43}',
    'Heroku API Key': r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}',
    'Generic Hex Secret (32)': r'[0-9a-f]{32}',
    'Generic Hex Secret (40)': r'[0-9a-f]{40}',
    'Generic Hex Secret (64)': r'[0-9a-f]{64}',
    'URL with token': r'https?://[^\s"']+\?[^\s"']*(token|key|secret|api)=[^\s"'&]+',
}

# Palabras clave para búsqueda de contexto
KEYWORD_PATTERNS = {
    'API Key mention': r'(?i)(api[_-]?key|apikey)',
    'Secret mention': r'(?i)(secret[_-]?key|secretkey|client_secret)',
    'Token mention': r'(?i)(access[_-]?token|auth[_-]?token|bearer_token|token)',
    'Password mention': r'(?i)(password|passwd|pwd)\s*[:=]',
    'Private key mention': r'(?i)(private[_-]?key)',
    'Credential mention': r'(?i)(credential)',
}

# Archivos sensibles por nombre
SENSITIVE_FILE_PATTERNS = [
    r'\.env',
    r'\.env\.\w+',
    r'.*\.pem$',
    r'.*\.key$',
    r'.*\.p12$',
    r'.*\.crt$',
    r'.*\.cer$',
    r'.*\.tfstate$',
    r'secrets?\.\w+$',
    r'credentials?\.\w+$',
    r'.*keystore.*',
    r'id_rsa',
    r'id_dsa',
    r'id_ecdsa',
    r'id_ed25519',
]

# Colores para terminal
class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'
    MAGENTA = '\033[95m'
    BOLD = '\033[1m'
    RESET = '\033[0m'

def color(text, c):
    return f"{c}{text}{Colors.RESET}"

def print_section(title):
    print(f"\n{'='*70}")
    print(color(f"🔍 {title}", Colors.CYAN + Colors.BOLD))
    print('='*70)

def print_finding(severity, file, line_num, line, pattern_name=""):
    color_map = {'CRITICAL': Colors.RED, 'HIGH': Colors.RED, 'MEDIUM': Colors.YELLOW, 'LOW': Colors.GREEN}
    sev_color = color_map.get(severity, Colors.YELLOW)
    prefix = color(f"[{severity}]", sev_color + Colors.BOLD)
    pattern_info = f" [{pattern_name}]" if pattern_name else ""
    print(f"{prefix}{pattern_info}")
    print(f"   📁 {color(file, Colors.CYAN)}:{color(str(line_num), Colors.MAGENTA)}")
    # Truncar línea larga
    display_line = line.strip()[:150] + "..." if len(line.strip()) > 150 else line.strip()
    print(f"   📝 {display_line}")
    print()

# ═══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 1: Archivos sensibles en git
# ═══════════════════════════════════════════════════════════════════════════════

def check_sensitive_files_in_git():
    print_section("1. Archivos sensibles trackeados en git")
    try:
        result = subprocess.run(['git', 'ls-files'], capture_output=True, text=True, encoding='utf-8', errors='replace')
        if result.returncode != 0:
            print(color("⚠️  No se pudo ejecutar 'git ls-files'. ¿Estás en un repositorio git?", Colors.YELLOW))
            return

        tracked_files = result.stdout.splitlines()
        found = []
        for f in tracked_files:
            for pattern in SENSITIVE_FILE_PATTERNS:
                if re.search(pattern, f, re.IGNORECASE):
                    found.append(f)
                    break

        if found:
            print(color(f"❌ {len(found)} archivo(s) sensible(s) encontrado(s) en git:", Colors.RED + Colors.BOLD))
            for f in found:
                print(f"   🔴 {f}")
        else:
            print(color("✅ Ningún archivo sensible encontrado en git", Colors.GREEN))
    except Exception as e:
        print(color(f"⚠️  Error: {e}", Colors.YELLOW))

# ═══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 2: Patrones de secrets en código
# ═══════════════════════════════════════════════════════════════════════════════

def scan_files_for_secrets(root_dir='.'):
    print_section("2. Escaneo de secrets en archivos de código")

    findings = []
    files_scanned = 0

    for dirpath, dirnames, filenames in os.walk(root_dir):
        # Excluir directorios
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]

        for filename in filenames:
            ext = Path(filename).suffix.lower()
            if ext not in EXTENSIONS:
                continue

            filepath = os.path.join(dirpath, filename)
            rel_path = os.path.relpath(filepath, root_dir)
            files_scanned += 1

            try:
                with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                    lines = f.readlines()
            except Exception:
                continue

            for line_num, line in enumerate(lines, 1):
                # Verificar patrones de secrets reales
                for pattern_name, pattern in SECRET_PATTERNS.items():
                    matches = re.finditer(pattern, line)
                    for match in matches:
                        # Filtrar falsos positivos comunes
                        if is_likely_false_positive(match.group(), line, pattern_name):
                            continue

                        severity = 'CRITICAL' if pattern_name in ['OpenAI API Key', 'AWS Access Key ID', 'AWS Secret Access Key', 
                                                                   'Private Key', 'GitHub PAT', 'Connection String'] else 'HIGH'
                        findings.append({
                            'severity': severity,
                            'file': rel_path,
                            'line_num': line_num,
                            'line': line,
                            'pattern': pattern_name,
                            'match': match.group()
                        })

                # Verificar menciones de keywords (menor severidad)
                for kw_name, kw_pattern in KEYWORD_PATTERNS.items():
                    if re.search(kw_pattern, line):
                        # Solo reportar si parece tener un valor asignado
                        if re.search(r'[:=]\s*["'][^"']{4,}["']', line) or re.search(r'[:=]\s*[a-zA-Z0-9_\-]{8,}', line):
                            # Verificar que no sea ya un finding de secret
                            already_found = any(f['line_num'] == line_num and f['file'] == rel_path for f in findings)
                            if not already_found:
                                findings.append({
                                    'severity': 'MEDIUM',
                                    'file': rel_path,
                                    'line_num': line_num,
                                    'line': line,
                                    'pattern': kw_name,
                                    'match': ''
                                })

    print(color(f"📊 Archivos escaneados: {files_scanned}", Colors.CYAN))

    if findings:
        # Ordenar por severidad
        severity_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
        findings.sort(key=lambda x: severity_order.get(x['severity'], 99))

        critical = sum(1 for f in findings if f['severity'] == 'CRITICAL')
        high = sum(1 for f in findings if f['severity'] == 'HIGH')
        medium = sum(1 for f in findings if f['severity'] == 'MEDIUM')

        print(color(f"❌ {len(findings)} hallazgo(s): {critical} CRÍTICO(S), {high} ALTO(S), {medium} MEDIO(S)", Colors.RED + Colors.BOLD))
        print()

        for f in findings[:50]:  # Limitar a 50 para no saturar
            print_finding(f['severity'], f['file'], f['line_num'], f['line'], f['pattern'])
            if f['match']:
                print(f"   🔑 Match: {color(f['match'], Colors.YELLOW)}")

        if len(findings) > 50:
            print(color(f"... y {len(findings) - 50} hallazgos más. Revisa manualmente.", Colors.YELLOW))
    else:
        print(color("✅ Ningún secret encontrado en el código", Colors.GREEN))

    return findings

def is_likely_false_positive(match, line, pattern_name):
    """Filtra falsos positivos comunes"""
    # Ejemplos en comentarios de documentación
    false_positive_patterns = [
        r'example',
        r'placeholder',
        r'your_',
        r'my_',
        r'xxx',
        r'123456',
        r'todo',
        r'fixme',
        r'dummy',
        r'sample',
        r'test_',
        r'fake_',
        r'mock_',
        r'demo',
        r'changeme',
        r'replace_this',
        r'insert_',
        r'YOUR_',
        r'MY_',
    ]

    line_lower = line.lower()
    for fp in false_positive_patterns:
        if fp in line_lower:
            return True

    # Password en variables de ejemplo
    if pattern_name == 'Password in code':
        if re.search(r'(?i)(example|placeholder|default|admin|root|password123|123456)', line):
            return True

    # Hex que sean hashes comunes (SHA-256 de archivos, etc.)
    if 'Generic Hex Secret' in pattern_name:
        if 'sha256' in line_lower or 'sha512' in line_lower or 'hash' in line_lower or 'checksum' in line_lower:
            return True

    return False

# ═══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 3: Archivos grandes en historial
# ═══════════════════════════════════════════════════════════════════════════════

def check_large_files_in_history():
    print_section("3. Archivos grandes (>1MB) en historial de git")
    try:
        result = subprocess.run(
            ['git', 'rev-list', '--objects', '--all'],
            capture_output=True, text=True, encoding='utf-8', errors='replace'
        )
        if result.returncode != 0:
            print(color("⚠️  No se pudo acceder al historial de git", Colors.YELLOW))
            return

        objects = result.stdout.strip().split('\n')
        large_files = []

        for obj in objects[:5000]:  # Limitar para rendimiento
            parts = obj.split()
            if len(parts) >= 2:
                sha = parts[0]
                filename = ' '.join(parts[1:])

                # Obtener tamaño
                size_result = subprocess.run(
                    ['git', 'cat-file', '-s', sha],
                    capture_output=True, text=True
                )
                if size_result.returncode == 0:
                    try:
                        size = int(size_result.stdout.strip())
                        if size > 1048576:  # 1MB
                            large_files.append((size, filename))
                    except ValueError:
                        pass

        if large_files:
            print(color(f"⚠️  {len(large_files)} archivo(s) grande(s) encontrado(s):", Colors.YELLOW))
            for size, filename in sorted(large_files, reverse=True)[:20]:
                print(f"   📦 {size/1048576:.2f} MB → {filename}")
        else:
            print(color("✅ Ningún archivo grande encontrado en el historial", Colors.GREEN))
    except Exception as e:
        print(color(f"⚠️  Error: {e}", Colors.YELLOW))

# ═══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 4: Commits con palabras sensibles
# ═══════════════════════════════════════════════════════════════════════════════

def check_sensitive_commits():
    print_section("4. Commits recientes con palabras sensibles")
    try:
        result = subprocess.run(
            ['git', 'log', '--all', '--oneline', '-100'],
            capture_output=True, text=True, encoding='utf-8', errors='replace'
        )
        if result.returncode != 0:
            print(color("⚠️  No se pudo acceder al historial de commits", Colors.YELLOW))
            return

        sensitive_keywords = ['secret', 'key', 'token', 'password', 'credential', 'env', 
                              'api_key', 'auth', 'private', 'leak', 'expose', 'remove']

        suspicious = []
        for line in result.stdout.splitlines():
            line_lower = line.lower()
            for kw in sensitive_keywords:
                if kw in line_lower:
                    suspicious.append(line)
                    break

        if suspicious:
            print(color(f"⚠️  {len(suspicious)} commit(s) con palabras sensibles:", Colors.YELLOW))
            for c in suspicious[:20]:
                print(f"   📝 {c}")
        else:
            print(color("✅ Ningún commit sospechoso encontrado", Colors.GREEN))
    except Exception as e:
        print(color(f"⚠️  Error: {e}", Colors.YELLOW))

# ═══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 5: Verificar archivos no trackeados sensibles
# ═══════════════════════════════════════════════════════════════════════════════

def check_untracked_sensitive_files():
    print_section("5. Archivos sensibles NO trackeados (working directory)")
    try:
        result = subprocess.run(
            ['git', 'status', '--porcelain'],
            capture_output=True, text=True, encoding='utf-8', errors='replace'
        )
        if result.returncode != 0:
            print(color("⚠️  No se pudo obtener git status", Colors.YELLOW))
            return

        untracked = []
        for line in result.stdout.splitlines():
            if line.startswith('??') or line.startswith('!!'):
                filepath = line[3:].strip()
                for pattern in SENSITIVE_FILE_PATTERNS:
                    if re.search(pattern, filepath, re.IGNORECASE):
                        untracked.append(filepath)
                        break

        if untracked:
            print(color(f"⚠️  {len(untracked)} archivo(s) sensible(s) NO trackeado(s):", Colors.YELLOW))
            for f in untracked:
                print(f"   🟡 {f}")
            print(color("   💡 Estos NO están en git todavía. Asegúrate de que .gitignore los excluya.", Colors.CYAN))
        else:
            print(color("✅ Ningún archivo sensible sin trackear", Colors.GREEN))
    except Exception as e:
        print(color(f"⚠️  Error: {e}", Colors.YELLOW))

# ═══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 6: Verificar .gitignore
# ═══════════════════════════════════════════════════════════════════════════════

def check_gitignore():
    print_section("6. Verificación de .gitignore")
    gitignore_path = Path('.gitignore')

    if not gitignore_path.exists():
        print(color("❌ No existe .gitignore", Colors.RED + Colors.BOLD))
        return

    try:
        content = gitignore_path.read_text(encoding='utf-8', errors='replace')
        required_patterns = [
            '.env', '*.pem', '*.key', '*.p12', '*.crt', 
            '__pycache__', 'node_modules', 'venv', '.pytest_cache'
        ]

        missing = []
        for pattern in required_patterns:
            if pattern not in content:
                missing.append(pattern)

        if missing:
            print(color(f"⚠️  .gitignore existe pero FALTAN {len(missing)} patrón(es) recomendado(s):", Colors.YELLOW))
            for p in missing:
                print(f"   🟡 {p}")
        else:
            print(color("✅ .gitignore cubre los patrones sensibles básicos", Colors.GREEN))
    except Exception as e:
        print(color(f"⚠️  Error leyendo .gitignore: {e}", Colors.YELLOW))

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    print(color("""
╔══════════════════════════════════════════════════════════════════════╗
║        🔐 CIPS SECRET AUDITOR v1.0                                   ║
║        Auditoría de seguridad para Content Intelligence System       ║
╚══════════════════════════════════════════════════════════════════════╝
    """, Colors.CYAN + Colors.BOLD))

    # Verificar que estamos en un repo git
    if not Path('.git').exists():
        print(color("❌ No parece ser un repositorio git (.git no encontrado)", Colors.RED))
        print(color("   Ejecuta este script desde la raíz del repositorio CIPS", Colors.YELLOW))
        sys.exit(1)

    check_sensitive_files_in_git()
    findings = scan_files_for_secrets()
    check_large_files_in_history()
    check_sensitive_commits()
    check_untracked_sensitive_files()
    check_gitignore()

    print(color("""
╔══════════════════════════════════════════════════════════════════════╗
║        📋 RESUMEN DE AUDITORÍA                                       ║
╚══════════════════════════════════════════════════════════════════════╝
    """, Colors.CYAN + Colors.BOLD))

    if findings:
        critical = sum(1 for f in findings if f['severity'] == 'CRITICAL')
        high = sum(1 for f in findings if f['severity'] == 'HIGH')
        print(color(f"   ❌ SECRETS ENCONTRADOS: {len(findings)} (Críticos: {critical}, Altos: {high})", Colors.RED + Colors.BOLD))
        print(color("   🔴 ACCIÓN REQUERIDA: Revisa los hallazgos arriba y rota las credenciales expuestas.", Colors.RED))
    else:
        print(color("   ✅ NO SE ENCONTRARON SECRETS EN EL CÓDIGO", Colors.GREEN + Colors.BOLD))

    print(color("""
   💡 Recomendaciones:
      1. Si encontraste secrets, rótalos (revoca) inmediatamente.
      2. Usa variables de entorno (.env) NUNCA commiteadas.
      3. Instala pre-commit hooks con gitleaks.
      4. Activa GitHub Secret Scanning en tu repo.
    """, Colors.CYAN))

if __name__ == '__main__':
    main()
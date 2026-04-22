#!/usr/bin/env python3
"""
Script pour trouver les appels subprocess restants dans les écrans.
Usage: python3 check_subprocess.py
"""

import os
import re
import sys

def find_subprocess_calls(directory):
    """Trouve tous les appels subprocess dans les fichiers Python."""
    subprocess_patterns = [
        r'subprocess\.run\(',
        r'subprocess\.call\(',
        r'subprocess\.check_output\(',
        r'subprocess\.Popen\(',
        r'os\.system\(',
        r'os\.popen\(',
    ]
    
    results = []
    
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                    for pattern in subprocess_patterns:
                        matches = re.finditer(pattern, content)
                        for match in matches:
                            # Trouver la ligne
                            lines = content[:match.start()].count('\n')
                            line_number = lines + 1
                            line_content = content.split('\n')[lines] if lines < len(content.split('\n')) else ''
                            
                            results.append({
                                'file': filepath,
                                'pattern': pattern,
                                'line': line_number,
                                'content': line_content.strip()
                            })
    
    return results

def main():
    # Chemin vers les écrans UI
    screens_dir = "fsdeploy/lib/ui/screens"
    
    if not os.path.exists(screens_dir):
        print(f"Erreur: Le répertoire {screens_dir} n'existe pas.")
        sys.exit(1)
    
    print("Recherche des appels subprocess dans les écrans...")
    print("=" * 80)
    
    results = find_subprocess_calls(screens_dir)
    
    if not results:
        print("✅ Aucun appel subprocess trouvé. Tous les écrans sont migrés !")
        return
    
    print(f"❌ Trouvé {len(results)} appels subprocess à migrer :")
    print()
    
    # Grouper par fichier
    files = {}
    for result in results:
        file = result['file']
        if file not in files:
            files[file] = []
        files[file].append(result)
    
    for file, calls in files.items():
        print(f"📄 {file}:")
        for call in calls:
            print(f"   Ligne {call['line']}: {call['content']}")
        print()
    
    print("=" * 80)
    print("RECOMMANDATIONS :")
    print("1. Pour chaque appel subprocess.run(), utiliser :")
    print("   ticket_id = self.bridge.emit('nom.evenement', callback=self._on_resultat)")
    print("2. Pour os.system(), utiliser le même pattern")
    print("3. Voir detection.py pour un exemple complet")

if __name__ == "__main__":
    main()

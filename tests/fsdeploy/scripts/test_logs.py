#!/usr/bin/env python3
"""
Script de test pour le système de logs compressés.
"""

import sys
sys.path.insert(0, '.')

from fsdeploy.lib.scheduler.intentlog.log import get_global_huffman_store

def main():
    hstore = get_global_huffman_store()
    # Enregistrer quelques événements
    hstore.log_event('test.parallel', severity='info', note='début optimisation')
    hstore.log_event('test.serial', severity='debug', source='script')
    hstore.log_task('task1', 'started', severity='info', task_class='TestTask')
    hstore.log_task('task1', 'completed', severity='info')
    
    # Afficher les stats
    stats = hstore.stats()
    print("Statistiques du HuffmanStore:")
    print(f"  Total records: {stats.get('total_records')}")
    print(f"  Total bytes: {stats.get('total_bytes')}")
    print(f"  Compression ratio: {stats.get('compression_ratio'):.3f}")
    print("\nComptes par sévérité:")
    for sev, cnt in stats.get('severity_counts', {}).items():
        print(f"  {sev}: {cnt}")
    
    # Exporter en JSON
    import tempfile
    import json
    import os
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        out_path = f.name
    hstore.export_json(out_path, table='all', severity='info')
    print(f"\nExport JSON généré : {out_path}")
    # Afficher quelques lignes
    with open(out_path, 'r') as f:
        data = json.load(f)
        print(f"Nombre d'entrées exportées : {len(data)}")
        if data:
            print("Première entrée:")
            print(json.dumps(data[0], indent=2))
    os.unlink(out_path)
    
    # Test de l'intent_log
    from fsdeploy.lib.scheduler.intentlog.log import intent_log
    print("\nStatistiques intent_log:")
    print(f"  total_entries: {intent_log.total_count}")
    print(f"  severity_counts: {intent_log.severity_counts()}")
    
    print("\nTest réussi.")

if __name__ == '__main__':
    main()

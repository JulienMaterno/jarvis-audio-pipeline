"""
Manage processed files tracking - view, clear, or remove specific files
"""
import sys
import json

def manage_processed_files():
    """Interactive tool to manage processed files tracking"""
    
    print("\n" + "="*60)
    print("PROCESSED FILES MANAGEMENT")
    print("="*60 + "\n")
    
    print("This tool helps you manage which files Jarvis has processed.")
    print("Files are tracked in Airflow Variables to prevent reprocessing.\n")
    
    print("Options:")
    print("1. View processed files")
    print("2. Clear all processed files (reprocess everything)")
    print("3. Remove specific file from tracking (reprocess one file)")
    print("4. Exit")
    
    choice = input("\nEnter choice (1-4): ").strip()
    
    if choice == "1":
        view_processed_files()
    elif choice == "2":
        clear_all_processed_files()
    elif choice == "3":
        remove_specific_file()
    elif choice == "4":
        print("Exiting...")
    else:
        print("Invalid choice!")

def view_processed_files():
    """View all processed files"""
    print("\n" + "-"*60)
    print("To view processed files, run this in Docker:")
    print("-"*60)
    print('docker exec jarvis-airflow-webserver-1 airflow variables get jarvis_processed_files')
    print("\nOr go to Airflow UI: http://localhost:8080")
    print("Admin → Variables → jarvis_processed_files")

def clear_all_processed_files():
    """Clear all processed files"""
    confirm = input("\n⚠️  Clear ALL processed files? This will reprocess everything! (yes/no): ").strip().lower()
    
    if confirm == "yes":
        print("\n" + "-"*60)
        print("Run this command to clear all processed files:")
        print("-"*60)
        print('docker exec jarvis-airflow-webserver-1 airflow variables set jarvis_processed_files "[]"')
        print("\nOr delete the variable in Airflow UI:")
        print("http://localhost:8080 → Admin → Variables → Delete jarvis_processed_files")
    else:
        print("Cancelled.")

def remove_specific_file():
    """Remove a specific file from processed tracking"""
    print("\n" + "-"*60)
    print("To remove a specific file from tracking:")
    print("-"*60)
    
    print("\n1. First, get the current list:")
    print('   docker exec jarvis-airflow-webserver-1 airflow variables get jarvis_processed_files')
    
    print("\n2. Copy the output and remove the file ID you want to reprocess")
    
    print("\n3. Set it back:")
    print('   docker exec jarvis-airflow-webserver-1 airflow variables set jarvis_processed_files \'["file_id_1", "file_id_2"]\'')
    
    print("\n4. Or use this Python helper:")
    print_python_helper()

def print_python_helper():
    """Print Python code to remove specific file"""
    helper_code = '''
# Remove specific file from processed tracking
docker exec jarvis-airflow-webserver-1 python3 << 'EOF'
from airflow.models import Variable
import json

# Get current processed files
processed = json.loads(Variable.get('jarvis_processed_files', default_var='[]'))
print(f"Current processed files: {len(processed)}")
print("\\nFiles:")
for i, file_id in enumerate(processed, 1):
    print(f"  {i}. {file_id}")

# Remove specific file (change this ID)
file_to_remove = "YOUR_FILE_ID_HERE"  # Change this!

if file_to_remove in processed:
    processed.remove(file_to_remove)
    Variable.set('jarvis_processed_files', json.dumps(processed))
    print(f"\\n✅ Removed {file_to_remove}")
else:
    print(f"\\n❌ File not found: {file_to_remove}")
EOF
'''
    print("\nHelper script:")
    print(helper_code)

if __name__ == "__main__":
    manage_processed_files()

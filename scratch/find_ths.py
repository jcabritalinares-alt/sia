with open('templates/historial.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if '<th' in line or '</th' in line:
        print(f"Line {i+1}: {line.strip()}")

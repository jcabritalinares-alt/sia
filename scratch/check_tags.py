with open('templates/historial.html', 'r', encoding='utf-8') as f:
    text = f.read()

for tag in ['div', 'table', 'tr', 'td', 'th', 'tbody', 'thead', 'form', 'script', 'style']:
    open_c = text.count('<' + tag)
    close_c = text.count('</' + tag + '>')
    print(f'{tag}: open={open_c}, close={close_c}')

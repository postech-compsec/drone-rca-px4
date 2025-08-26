## msg/versioned/make_publisherid_pubtimestamp.py ##

import os

# 현재 Python 파일과 같은 디렉토리 경로
msg_dir = os.path.dirname(os.path.abspath(__file__))
field1 = 'uint8 publisher_id'
field2 = 'uint64 pub_timestamp'

for filename in os.listdir(msg_dir):
    if filename.endswith('.msg'):
        file_path = os.path.join(msg_dir, filename)

        with open(file_path, 'r') as f:
            lines = f.readlines()

        if any(field1 in line for line in lines):
            print(f'{field1} already exists in {filename}')
            continue

        # 삽입 위치 찾기: 첫 번째 빈 줄 전
        insert_index = 0
        for i, line in enumerate(lines):
            if line.strip() == '':
                insert_index = i
                break
        else:
            insert_index = len(lines)

        lines.insert(insert_index, '\n' + field1 + '\n' + field2 + '\n')

        with open(file_path, 'w') as f:
            f.writelines(lines)

        print(f'Inserted {field1}, {field2} into {filename} at line {insert_index + 1}')

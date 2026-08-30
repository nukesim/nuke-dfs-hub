from pathlib import Path
p=Path('pages/6_SIM.py')
s=p.read_text(encoding='utf-8')
if 'import numpy as np\n' not in s:
    s=s.replace('import pandas as pd\n','import pandas as pd\nimport numpy as np\n',1)
p.write_text(s,encoding='utf-8')

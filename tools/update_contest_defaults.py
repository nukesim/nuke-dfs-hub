from pathlib import Path

p=Path('pages/6_SIM.py')
s=p.read_text()
s=s.replace('field_size=st.number_input("Field size",2,100000,2222,1,key="field_size")','field_size=st.number_input("Field size",2,1000000,654761,1,key="field_size")')
s=s.replace('entry_fee=st.number_input("Entry fee ($)",.25,10000.,100.,1.,key="entry_fee")','entry_fee=st.number_input("Entry fee ($)",.25,10000.,5.,1.,key="entry_fee")')
s=s.replace('first_prize=st.number_input("1st prize ($)",1.,10000000.,50000.,100.,key="first_prize")','first_prize=st.number_input("1st prize ($)",1.,10000000.,1000000.,100.,key="first_prize")')
p.write_text(s)

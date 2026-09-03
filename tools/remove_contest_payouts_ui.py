from pathlib import Path

path=Path('pages/6_SIM.py')
text=path.read_text(encoding='utf-8')
text=text.replace('from dk_contest_import import parse_payout_upload\n','')
old='''st.subheader("🏆 Contest Payouts")\npayout_upload=st.file_uploader(f"Optional: upload {cfg.name} payout CSV / Excel",type=["csv","xlsx","xls"],key=f"payout_upload_{site}")\npayouts_override=None\nif payout_upload is not None:\n    try:\n        payouts_override,payout_info=parse_payout_upload(payout_upload)\n        a,b,c=st.columns(3)\n        a.metric("Imported Paid Places",f"{int(payout_info['paid_places']):,}")\n        b.metric("Imported 1st",f"${float(payout_info['first_prize']):,.0f}")\n        c.metric("Imported Prize Pool",f"${float(payout_info['listed_prize_pool']):,.0f}")\n        st.success("Real payout ladder loaded.")\n    except Exception as e:\n        st.error(f"Could not parse payout file: {e}")\n        st.stop()\nelse:\n    st.caption("No payout file uploaded — NUKE will use the modeled GPP payout curve.")\n'''
if old not in text:
    raise SystemExit('Contest Payouts UI block not found')
text=text.replace(old,'payouts_override=None\n')
path.write_text(text,encoding='utf-8')
print('Removed Contest Payouts upload UI; modeled contest simulation remains unchanged.')

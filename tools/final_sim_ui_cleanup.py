from pathlib import Path
import re

p=Path('pages/6_SIM.py')
s=p.read_text(encoding='utf-8')

# Remove duplicate overlap-stat assignments, preserving one copy of each.
for line in [
    '    median_overlap=float(np.median(overlap_vals)) if overlap_vals else 0.0\n',
    '    p95_overlap=float(np.percentile(overlap_vals,95)) if overlap_vals else 0.0\n',
    '    max_overlap_seen=int(max(overlap_vals)) if overlap_vals else 0\n',
]:
    first=s.find(line)
    if first!=-1:
        s=s[:first+len(line)] + s[first+len(line):].replace(line,'')

# Collapse repeated stage_times assignments.
s=re.sub(r'(stage_times=st\.session_state\.get\("nuke_stage_times",\{\}\)\n)(?:stage_times=st\.session_state\.get\("nuke_stage_times",\{\}\)\n)+',r'\1',s)

# Keep exactly one Run Performance block before Candidate Pool Health.
marker='if candidate_diag:\n'
pos=s.find(marker)
if pos!=-1:
    pre=s[:pos]
    post=s[pos:]
    first=pre.find('if stage_times:\n    st.subheader("⏱️ Run Performance")')
    if first!=-1:
        perf='''if stage_times:\n    st.subheader("⏱️ Run Performance")\n    total=float(st.session_state.get("nuke_sim_runtime",0.0))\n    timing_cols=st.columns(len(stage_times))\n    for col,(name,secs) in zip(timing_cols,stage_times.items()):\n        col.metric(name,f"{float(secs):.1f}s")\n    if total>0:\n        slow_name,slow_secs=max(stage_times.items(),key=lambda kv:kv[1])\n        st.caption(f"Total {total:.1f}s · Bottleneck: {slow_name} ({float(slow_secs):.1f}s, {100.0*float(slow_secs)/total:.0f}% of run).")\n\n'''
        s=pre[:first]+perf+post

p.write_text(s,encoding='utf-8')

# Self-disable the one-shot workflow before its commit.
w=Path('.github/workflows/final-sim-ui-cleanup.yml')
if w.exists():
    w.write_text('''name: Final SIM UI Cleanup\non:\n  workflow_dispatch:\njobs:\n  disabled:\n    if: ${{ false }}\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo "SIM UI cleanup completed."\n''',encoding='utf-8')

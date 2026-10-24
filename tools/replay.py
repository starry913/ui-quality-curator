"""Replay saved model responses only; never sends API requests."""
import html
import json
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
EXPERIMENTS=('landing-page-random-50','dashboard-random-50')

def main():
    links=[]
    for name in EXPERIMENTS:
        folder=ROOT/'experiments'/name
        completed=subprocess.run([sys.executable,str(folder/'build_report_v5.py')],capture_output=True,text=True,encoding='utf-8')
        if completed.returncode:
            sys.stderr.write(completed.stderr)
            return completed.returncode
        summary=json.loads((folder/'summary_v5.json').read_text(encoding='utf-8'))
        print(name,summary['quality_counts'],'mean:',summary['mean_total'])
        links.append('<li><a href="experiments/'+name+'/review.html">'+html.escape(name)+'</a> — '+html.escape(str(summary['quality_counts']))+'</li>')
    page='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>UI Quality Curator</title><style>body{max-width:850px;margin:60px auto;padding:0 24px;font:18px/1.8 system-ui;color:#222}a{color:#245b80}li{margin:18px 0}</style><h1>UI Quality Curator</h1><p>基于已保存的真实模型响应离线重算；本次没有调用 API。</p><ul>'+''.join(links)+'</ul><p>质量分档：高质量 ≥65；中质量 ≥50 且 &lt;65；低质量 &lt;50。原始图片不随代码发布，报告提供来源链接。</p></html>'
    (ROOT/'index.html').write_text(page,encoding='utf-8')
    return 0

if __name__=='__main__':raise SystemExit(main())

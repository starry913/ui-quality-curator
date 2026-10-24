import ast
import csv
import html
import json
import re
import shutil
from collections import Counter
from run_jev import ROOT, save_json
from run_structure_v5 import DIMENSIONS, STRUCTURE_NAMES, RULE, summarize_v5
from run_classification_v4 import FUNCTION_NAMES, DOMAIN_NAMES
from review_policy_v5 import POLICY, review_reasons

def read(name):return json.loads((ROOT/name).read_text(encoding='utf-8-sig'))
esc=lambda x:html.escape(str(x))
results=read('jev_results_v5.json');previous={x['sample_id']:x for x in read('jev_results_v4.json')}
captions={x['sample_id']:x for x in read('captions_structured_v5.json')}
with (ROOT/'samples.csv').open(encoding='utf-8-sig',newline='') as f:samples={x['sample_id']:x for x in csv.DictReader(f)}
assert len(results)==50 and {x['sample_id'] for x in results}==set(samples)
cards=[];client=[];exports=[];review_ids=[];old_review_ids=[]
for item in sorted(results,key=lambda x:x['sample_id']):
    sid=item['sample_id'];scores,total,quality,reasons=summarize_v5(previous[sid],item['structure_response']['answers'])
    item.update(scores=scores,total=total,quality=quality,reasons=reasons)
    function=item['page_function'];domain=item['business_domain'];kind=item['structure_kind']
    qa=item['response']['answers'];sa=item['structure_response']['answers']
    label={'high_quality':'高质量','medium_quality':'中质量','low_quality':'低质量'}[quality]
    review=review_reasons(item)
    if review:review_ids.append(sid)
    if any(qa[k]['confidence']<.6 for k in ('page_function','business_domain')) or sa['structure_kind']['confidence']<.6:old_review_ids.append(sid)
    accept_probability=sum(sa['structure_kind']['probabilities'][k] for k in POLICY['accepted_structures'])
    client.append({'id':sid,'func':function,'domain':domain,'kind':kind,'valid':qa['valid_ui']['noul'],'total':total,'design_total':item['design_total'],'structure_accept_probability':accept_probability,**scores})
    exports.append({'sample_id':sid,'quality':label,'page_function':FUNCTION_NAMES[function],'business_domain':DOMAIN_NAMES[domain],'structure_kind':STRUCTURE_NAMES[kind],'total':round(total,1),**{k:round(v,1) for k,v in scores.items()},'structure_confidence':sa['structure_kind']['confidence'],'needs_review':bool(review),'review_reasons':'；'.join(review)})
    metrics=''.join(f'<div class="metric"><div><span>{dim["label"]}</span><strong>{scores[k]:.1f}<small> / 100</small></strong></div><div class="track"><i style="width:{scores[k]:.3f}%"></i></div></div>' for k,dim in DIMENSIONS.items())
    details=''.join(f'<p><b>{esc(k)}：</b>{esc("；".join(v) if isinstance(v,list) else v)}</p>' for k,v in captions[sid].items() if k!='sample_id')
    note=f'<p class="review-note"{ "" if review else " hidden" }>需复核：{esc("；".join(review))}</p>'
    cards.append(f'''<article id="{sid}" data-id="{sid}"><div class="card-head"><b>{sid}</b><span class="quality {quality}">{label}</span></div><div class="tags"><span class="type">功能：{FUNCTION_NAMES[function]}</span><span class="type">领域：{DOMAIN_NAMES[domain]}</span><span class="type">结构：{STRUCTURE_NAMES[kind]}</span></div><a href="{esc(samples[sid]['sample_path'])}" target="_blank"><img loading="lazy" src="previews/{sid}.jpg" alt="{sid}"></a>{note}<div class="total"><span>综合筛选分</span><strong>{total:.1f}<small> / 100</small></strong></div><p>设计总分 {item['design_total']:.1f} / 100（保留上轮五项评分）</p><div class="metrics">{metrics}</div><p class="reason">{esc('；'.join(reasons))}</p><details><summary>查看描述与分类依据</summary>{details}<p>页面结构置信度 {sa['structure_kind']['confidence']:.2f} · 结构评分置信度 {sa['completeness']['confidence']:.2f} · 功能置信度 {qa['page_function']['confidence']:.2f} · 领域置信度 {qa['business_domain']['confidence']:.2f}</p></details></article>''')
save_json(ROOT/'jev_results_v5.json',results);save_json(ROOT/'rule_v5.json',RULE)
with (ROOT/'classification_scores_v5.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(exports[0]));w.writeheader();w.writerows(exports)
save_json(ROOT/'classification_scores_v5.json',exports)
summary={'round':5,'count':50,'quality_counts':dict(Counter(x['quality'] for x in exports)),'structure_counts':dict(Counter(x['structure_kind'] for x in exports)),'mean_total':round(sum(x['total'] for x in results)/50,1),'bottom10':[{'sample_id':x['sample_id'],'total':round(x['total'],1),'structure_kind':STRUCTURE_NAMES[x['structure_kind']]} for x in sorted(results,key=lambda x:x['total'])[:10]],'human_calibrated':False,'human_correction_ids':['LP006','LP030'],'rule':'rule_v5.json','new_api_calls':50}
summary.pop('new_api_calls',None)
summary['stored_requests']=2*len(results)
summary['report_api_calls']=0
save_json(ROOT/'summary_v5.json',summary)
summary['review']={'previous_count':len(old_review_ids),'count':len(review_ids),'ratio':len(review_ids)/50,'sample_ids':review_ids,'policy':'review_policy_v5.json'}
save_json(ROOT/'summary_v5.json',summary);save_json(ROOT/'review_policy_v5.json',POLICY)
tree=ast.parse((ROOT/'build_scores_report_v3.py').read_text(encoding='utf-8'))
template=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='template' for t in n.targets))
template=template.split('<script>')[0]
template=template.replace('前端图片筛选 · 100 分质量评分','前端页面筛选 · 结构完整度优先')
template=template.replace('总分 = 布局 25% + 层级 20% + 可读性 15% + 一致性 20% + 可学习性 20%','设计总分 = 布局25% + 层级20% + 可读性15% + 一致性20% + 可学习性20%。综合筛选分 = 设计总分、页面结构完整度与结构上限三者的最低值。孤立组件上限25，作者宣传与非界面上限0。')
template=template.replace('高质量：总分达到门槛、可学习性 ≥ 70','高质量：综合筛选分达到门槛、页面结构完整度 ≥ 70、可学习性 ≥ 70')
old='<select id="type" aria-label="类型筛选"><option value="all">全部类型</option>TYPEOPTIONS</select>'
new='<select id="function"><option value="all">全部页面功能</option>'+''.join(f'<option value="{k}">{v}</option>' for k,v in FUNCTION_NAMES.items())+'</select><select id="domain"><option value="all">全部业务领域</option>'+''.join(f'<option value="{k}">{v}</option>' for k,v in DOMAIN_NAMES.items())+'</select>'
assert old in template;template=template.replace(old,new)
template=template.replace('HIGHCOUNT',str(summary['quality_counts'].get('高质量',0))).replace('LOWCOUNT',str(summary['quality_counts'].get('低质量',0))).replace('MEAN',str(summary['mean_total'])).replace('SORTOPTIONS',''.join(f'<option value="{k}">按{v["label"]}排序</option>' for k,v in DIMENSIONS.items())+'<option value="design_total">按设计总分排序</option>').replace('CARDS',''.join(cards))
template=template.replace('</style>','.tags{margin-bottom:10px}.review-note{color:#9a5b00;background:#fff6df;padding:8px}.card-head>.quality{font-size:12px;padding:4px 8px;border-radius:6px}</style>')
template=template.replace('各项满分 100，置信度单独保留。','各项满分100，显示一位小数。结构分类为辅助筛选依据；保留五项设计分，额外调用Jev评估页面结构。置信度不等于正确率。')
template=template.replace('</header>','<p class="formula" id="review-count">需复核 '+str(len(review_ids))+' / 50 张：只提示影响保留/淘汰的边界情况；分类置信度保留在详情。</p></header>')
script=(ROOT/'review_controls_v4.js').read_text(encoding='utf-8')
script=script.replace("r.func!=='non_ui'&&r.valid>=.7","r.kind!=='component'&&r.kind!=='promotion'&&r.completeness>=70&&r.func!=='non_ui'&&r.valid>=.7")
script=script.replace("const a=[];if(r.func", "const a=[];if(r.kind==='component')a.push('仅孤立组件/区块，综合分封顶25');if(r.kind==='promotion'||r.func==='non_ui')a.push('作者宣传或非界面：综合分为0');if(r.completeness<70)a.push('页面结构完整度低于70');if(r.func")
script=script.replace("'总分低于'","'综合筛选分低于'")
script=script.replace("'总分','布局与间距'","'综合筛选分','设计总分','页面结构完整度','布局与间距'")
script=script.replace("['total','layout'","['total','design_total','completeness','layout'")
review_script="""function reviewReasons(r){if(['component','promotion'].includes(r.kind)||r.func==='non_ui')return [];if(r.valid<.7||r.learnability<70||['layout','hierarchy','readability','consistency'].some(k=>r[k]<60))return [];const a=[];if(r.completeness>=70&&Math.abs(r.total-cutoff())<=1)a.push('综合分距高质量门槛不超过1分');if(r.design_total>=cutoff()&&r.structure_accept_probability>=.3&&r.structure_accept_probability<=.7)a.push('设计分达标，但页面结构能否接受仍不确定');return a}
function updateReview(){let count=0;for(const card of main.querySelectorAll('article')){const a=reviewReasons(byId.get(card.dataset.id)),note=card.querySelector('.review-note');note.hidden=!a.length;note.textContent='需复核：'+a.join('；');if(a.length)count++}document.getElementById('review-count').textContent='需复核 '+count+' / 50 张：只提示影响保留/淘汰的边界情况；分类置信度保留在详情。'}
"""
script=review_script+script
script=script.replace("function apply(){let high=0;","function apply(){updateReview();let high=0;")
header='const records='+json.dumps(client,ensure_ascii=False)+',functionNames='+json.dumps(FUNCTION_NAMES,ensure_ascii=False)+',domainNames='+json.dumps(DOMAIN_NAMES,ensure_ascii=False)+';\n'
template=template.replace('<option value="design_total">按设计总分排序</option>','')
for item in results:
    template=template.replace(f"<p>设计总分 {item['design_total']:.1f} / 100（保留上轮五项评分）</p>",'')
old_formula='设计总分 = 布局25% + 层级20% + 可读性15% + 一致性20% + 可学习性20%。综合筛选分 = 设计总分、页面结构完整度与结构上限三者的最低值。孤立组件上限25，作者宣传与非界面上限0。'
new_formula='质量总分满分100：布局25% + 层级20% + 可读性15% + 一致性20% + 可学习性20%，再受页面结构完整度限制。孤立组件最高25分，作者宣传与非界面为0分。'
assert old_formula in template
template=template.replace(old_formula,new_formula).replace('综合筛选分','质量总分').replace('综合分','质量总分')
script=script.replace("'综合筛选分','设计总分','页面结构完整度'","'质量总分','页面结构完整度'").replace("['total','design_total','completeness'","['total','completeness'")
script=script.replace('综合筛选分','质量总分').replace('综合分','质量总分').replace('设计分达标，但页面结构能否接受仍不确定','页面结构的判断可能影响保留结果')
page=template+'<script>'+header+script+'</script></body></html>'
template=template.replace('<span id="low">',f'<span id="medium">中质量 {summary["quality_counts"].get("中质量",0)} 张</span><span id="low">')
template=template.replace('<option value="low_quality">','<option value="medium_quality">中质量</option><option value="low_quality">')
template=re.sub(r'<label>高质量总分门槛 .*?</label>','',template)
template=re.sub(r'<p class="formula">高质量：.*?</p>','<p class="formula">按质量总分分档：高质量 ≥65；中质量 ≥50 且 &lt;65；低质量 &lt;50。分类按未舍入分数计算。</p>',template)
template=template.replace('</style>','.medium_quality{background:#fff2cc;color:#7a5b00}</style>')
template=template.replace('调整总分门槛只重新计算标签，不调用 API。','质量分档固定为65和50，不额外设置分项门槛。')
script=re.sub(r'function cutoff\(\)\{.*?\}\n','function cutoff(){return 65}\n',script)
script=re.sub(r'function quality\(r\)\{.*?\}\n',"function quality(r){return r.total>=65?'high_quality':r.total>=50?'medium_quality':'low_quality'}\n",script)
script=re.sub(r'function reason\(r\)\{.*?\}\n',"function reason(r){const a=[];if(r.kind==='component')a.push('仅孤立组件/区块，质量总分封顶25');if(r.kind==='promotion'||r.func==='non_ui')a.push('作者宣传或非界面：质量总分为0');a.push(r.total>=65?'质量总分≥65：高质量':r.total>=50?'50≤质量总分<65：中质量':'质量总分<50：低质量');return a.join('；')}\n",script)
script=re.sub(r'function reviewReasons\(r\)\{.*?\}\n',"function reviewReasons(r){if(['component','promotion'].includes(r.kind)||r.func==='non_ui')return [];const a=[];if([50,65].some(t=>Math.abs(r.total-t)<=1))a.push('质量总分距50或65分界线不超过1分');if(r.design_total>=65&&r.structure_accept_probability>=.3&&r.structure_accept_probability<=.7)a.push('页面结构的判断可能影响保留结果');return a}\n",script)
script=script.replace('let high=0;visible=[];','let high=0,medium=0;visible=[];').replace("if(value==='high_quality')high++;","if(value==='high_quality')high++;if(value==='medium_quality')medium++;")
script=script.replace("value==='high_quality'?'高质量':'低质量'","value==='high_quality'?'高质量':value==='medium_quality'?'中质量':'低质量'")
script=script.replace("document.getElementById('low').textContent='低质量 '+(50-high)+' 张'","document.getElementById('medium').textContent='中质量 '+medium+' 张';document.getElementById('low').textContent='低质量 '+(50-high-medium)+' 张'")
script=script.replace('sortSelect,direction,threshold]','sortSelect,direction]').replace("quality(r)==='high_quality'?'高质量':'低质量'","quality(r)==='high_quality'?'高质量':quality(r)==='medium_quality'?'中质量':'低质量'")
script=script.replace("'总分门槛'","'分档标准'").replace(',cutoff()]);',",'高≥65；中50–65；低<50']);").replace("'前端图片功能领域与分数_门槛'+cutoff()+'.csv'","'前端图片质量三档分类.csv'")
page=template+'<script>'+header+script+'</script></body></html>'
script=script.replace('function reviewReasons(r){',"function reviewReasons(r){if(['layout','hierarchy','readability','consistency'].some(k=>r[k]<50))return [];")
script=script.replace("a.push(r.total>=65?","for(const [k,n] of [['layout','布局与间距'],['hierarchy','信息层级'],['readability','可读性'],['consistency','视觉一致性']])if(r[k]<50)a.push(n+'低于50，质量总分上限'+r[k].toFixed(1));a.push(r.total>=65?")
template=template.replace('孤立组件最高25分，作者宣传与非界面为0分。','孤立组件最高25分，作者宣传与非界面为0分。布局、层级、可读性或一致性任一低于50时，总分不能高于该项分数。')
page=template+'<script>'+header+script+'</script></body></html>'
archive=ROOT/'review_round4.html'
if not archive.exists() and (ROOT/'review.html').exists():shutil.copy2(ROOT/'review.html',archive)
# Original third-party images are deliberately not redistributed in this repository.
for sample_id, sample in samples.items():
    if not (ROOT/'previews'/f'{sample_id}.jpg').is_file():
        pattern=r'<a href="[^"]*" target="_blank"><img loading="lazy" src="previews/'+re.escape(sample_id)+r'\.jpg" alt="'+re.escape(sample_id)+r'"></a>'
        source_url=sample.get('shot_url','')
        if source_url.startswith('https://dribbble.com/'):
            replacement='<p><a href="'+esc(source_url)+'" target="_blank" rel="noopener noreferrer">原图未随代码发布 · 查看来源作品</a></p>'
        else:
            replacement='<p>原图未随代码发布；可将自有预览放入 previews/。</p>'
        page=re.sub(pattern,lambda match:replacement,page)
page=page.replace('所有原图与历次实验结果保留。','仓库保留描述和评分记录；原图需自行提供。')
(ROOT/'review.html').write_text(page,encoding='utf-8')
(ROOT/'review_script_v5.js').write_text(header+script,encoding='utf-8')
assert page.count('<article ')==50 and page.count('class="metric"')==300
experiment=read('experiment.json');experiment['round5']={**summary,'results':'jev_results_v5.json','export':'classification_scores_v5.csv','caption':'captions_structured_v5.json','original_images_preserved':True,'prior_report':'review_round4.html'};save_json(ROOT/'experiment.json',experiment)
print(json.dumps(summary,ensure_ascii=False,indent=2))

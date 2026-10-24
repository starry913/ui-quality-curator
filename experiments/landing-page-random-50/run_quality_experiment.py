import csv
import json
import time
import shutil
import urllib.request
import urllib.error
from pathlib import Path
from run_jev import ROOT, WORKSPACE, save_json

QUESTIONS = {
    'valid_ui': {'type':'noul','instructions':'图片是否提供足够可辨认的网页/应用界面，可学习布局或组件？纯logo、品牌照片、点赞感谢宣传、色板都应为否。网页内正常的产品摄影和插画不应排除。根据具体视觉证据判断，不按来源分类猜测。'},
    'learnability': {'type':'score','instructions':'评价图中的前端结构和细节是否足够用于模型学习。不要把缩略显示时小字不清当成原图模糊。样机、拼图、局部区段本身不扣分；看主要UI实际是否可辨认。','criteria':[
        '没有足够可辨认的前端界面，仅logo、宣传文字、照片等',
        '界面信息很少或主要UI太小、严重变形/遮挡，只能辨认风格，难以学习布局组件',
        '至少一个完整区段或主要布局可辨认，多数关键组件关系可学习，允许局部小字不清',
        '主要布局和组件细节清楚，层级关系充分，可学习丰富的页面组织或组件设计']},
    'hierarchy': {'type':'score','instructions':'仅评价界面信息层级。基于标题、正文、按钮、内容分组的具体视觉证据，不根据赞美词猜测。','criteria':[
        '没有有效UI或内容无法观察',
        '主次不清或证据不足，难以确认清晰层级',
        '标题正文操作入口有明确主次，分组清楚',
        '层级成熟且有节奏，清晰引导主要内容和操作']},
    'layout': {'type':'score','instructions':'评价界面自身的布局、对齐、间距秩序。外部样机倾斜和拼图排布不是界面错位；不必要求完整页面。','criteria':[
        '没有有效UI或无法观察布局',
        '明显拥挤、错位、间距失衡，或证据不足以确认秩序',
        '主要元素对齐合理、分组间距有秩序，足够清晰',
        '对齐间距成熟一致，留白和视觉平衡经过精细组织']},
    'consistency': {'type':'score','instructions':'评价界面字体、配色和可见组件的一致性。多样色块、强调字体和插画不等于混乱；依据具体是否协调。','criteria':[
        '没有有效UI或无法观察设计语言',
        '字体颜色组件明显冲突或缺少足够证据',
        '字体配色及可见组件协调，主视觉语言统一',
        '字体配色组件构成稳定成熟的设计语言，细节统一']},
    'severe_defect': {'type':'noul','instructions':'主要界面是否有严重、实际可观察的模糊、透视变形、遮挡或裁切，以致无法学习多数关键布局与组件？普通边缘裁切、正常网页弹窗、装饰、轻微透视、小字在预览时无法读、未知项都不等于严重缺陷。'},
    'page_use': {'type':'choice','instructions':'按主要页面用途选一个类别，不按行业或来源。先排除非界面；电商需要购物/商品浏览购买用途；业务管理需要以操作界面为主，营销页内嵌dashboard示意图仍归营销；摄影作品集归内容/作品集。','criteria':{
        'marketing':'产品、服务、机构或品牌的对外介绍、获客、推广页面，含营销区段和服务预订首屏',
        'commerce':'主要服务于购物，包括商店首页、商品浏览列表、商品详情、购物车、支付结算',
        'operations':'主要服务于业务操作或数据分析，包括后台、dashboard、管理、CRM操作界面',
        'content':'主要服务于内容阅读展示或个人/创作作品集，包括文章、媒体、摄影作品集',
        'other':'确有界面，但主要用途不属于以上或证据不足，如独立登录/设置或无法辨认用途',
        'non_ui':'主要是纯品牌标志、照片、色板、点赞感谢/作者宣传横幅，没有足够界面结构'}}
}
RULE = {
    'version':'quality-v2.1',
    'objective':'筛选可学习前端布局组件且视觉设计成熟的图片；不评价网站真实可用性、代码正确性或版权',
    'high_quality_requirements':{
        'valid_ui_probability_at_least':0.7,
        'each_of_learnability_hierarchy_layout_consistency_probability_of_level_2_or_3_at_least':0.65,
        'severe_defect_probability_below':0.65,
        'page_use_not':'non_ui'},
    'otherwise':'low_quality',
    'notes':['阈值为试验规则，未由人工金标准校准。','0-3评分中的2表示达到清晰可用标准，3表示表现成熟。','使用每个维度等级2和3的概率之和，避免把概率加权均值当作离散等级。','描述缺少证据可能导致保守地判为低质量，不能当作原图真实质量结论。','只输出高质量/低质量和页面用途；分项分数是内部判断依据。']}

def classify(answers):
    acceptable={name:sum(answers[name]['probabilities'].get(str(level),0) for level in (2,3)) for name in ('learnability','hierarchy','layout','consistency')}
    reasons=[]
    if answers['valid_ui']['noul']<0.7 or answers['page_use']['choice']=='non_ui':
        reasons.append('缺少足够有效的前端界面信息')
    if answers['page_use']['choice']=='non_ui':
        return 'low_quality',reasons
    if acceptable['learnability']<0.65:
        reasons.append('可学习的结构或细节不足')
    for name,label in [('hierarchy','信息层级'),('layout','布局与间距'),('consistency','视觉一致性')]:
        if acceptable[name]<0.65:
            reasons.append(label+'达标的证据不足')
    if answers['severe_defect']['noul']>=0.65:
        reasons.append('主要界面存在影响学习的严重缺陷')
    return ('low_quality' if reasons else 'high_quality'), reasons or ['结构细节可学习，层级、排版和视觉一致性达到本轮标准']

def main():
    captions={x['sample_id']:x for x in json.loads((ROOT/'captions_luna.json').read_text(encoding='utf-8-sig'))}
    evidence={x['sample_id']:x for x in json.loads((ROOT/'quality_evidence_luna.json').read_text(encoding='utf-8-sig'))}
    with (ROOT/'samples.csv').open(encoding='utf-8-sig',newline='') as handle:
        expected={row['sample_id'] for row in csv.DictReader(handle)}
    if len(evidence)!=50 or set(evidence)!=expected:
        raise SystemExit('Quality evidence IDs must match all 50 samples')
    key=next((x.split('=',1)[1].strip().strip('"').strip("'") for x in (WORKSPACE/'.env').read_text(encoding='utf-8-sig').splitlines() if x.startswith('TYPESAFE_API_KEY=')),None)
    if not key:raise SystemExit('Missing API key')
    save_json(ROOT/'quality_questions_v2.json',QUESTIONS)
    previous_rule=ROOT/'quality_rule_v2.json'
    if previous_rule.exists() and not (ROOT/'quality_rule_v2_initial.json').exists():
        shutil.copy2(previous_rule,ROOT/'quality_rule_v2_initial.json')
    save_json(ROOT/'quality_rule_v2.json',RULE)
    output=ROOT/'jev_quality_results_v2.json'
    results=json.loads(output.read_text(encoding='utf-8')) if output.exists() else []
    for saved in results:
        saved.setdefault('initial_quality',saved['quality'])
        saved['quality'],saved['reasons']=classify(saved['response']['answers'])
        saved['rule_version']=RULE['version']
    if results:save_json(output,results)
    complete={x['sample_id'] for x in results}
    for sid in sorted(expected):
        if sid in complete:continue
        state={'visual_caption':{k:v for k,v in captions[sid].items() if k!='sample_id'},'quality_observations':{k:v for k,v in evidence[sid].items() if k!='sample_id'}}
        payload={'model':'jev-latest','state':state,'questions':QUESTIONS}
        request=urllib.request.Request('https://api.typesafe.ai/v1/systemone',data=json.dumps(payload,ensure_ascii=False).encode('utf-8'),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
        started=time.monotonic()
        try:
            with urllib.request.urlopen(request,timeout=45) as response:result=json.load(response)
        except urllib.error.HTTPError as error:
            raise SystemExit(f'HTTP {error.code} on {sid}; stopped with prior results saved') from None
        except urllib.error.URLError:
            raise SystemExit(f'Network error on {sid}; stopped with prior results saved') from None
        answers=result.get('answers',{})
        if set(answers)!=set(QUESTIONS):raise SystemExit('Unexpected answer schema')
        for name in ('learnability','hierarchy','layout','consistency'):
            if not 0<=answers[name]['score']<=3:raise SystemExit('Unexpected score range')
        quality,reasons=classify(answers)
        results.append({'sample_id':sid,'quality':quality,'type':answers['page_use']['choice'],'reasons':reasons,'rule_version':RULE['version'],'elapsed_seconds':round(time.monotonic()-started,3),'response':result})
        save_json(output,results)
        print(f'{sid} complete ({len(results)}/50)',flush=True)

if __name__=='__main__':main()

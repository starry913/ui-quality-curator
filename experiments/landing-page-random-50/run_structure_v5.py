import copy
import hashlib
import json
import time
import urllib.error
import urllib.request
from run_jev import ROOT, WORKSPACE, save_json, load_api_key
from run_classification_v4 import DIMENSIONS, FUNCTION_NAMES, DOMAIN_NAMES

DIMENSIONS=copy.deepcopy(DIMENSIONS)
DIMENSIONS['completeness']={'label':'页面结构完整度','weight':0}
STRUCTURE_NAMES={'full_page':'完整页面','main_viewport':'完整主视口/首屏','partial_page':'页面局部','component':'孤立组件/区块','promotion':'作者宣传/非界面','unknown':'结构无法确定'}
INSTRUCTION='目标是收集可学习完整页面组织的前端图片。判断实际可见结构，不相信caption中的“网页首屏”“页面”等名称。一个标题+说明+按钮+插画的孤立矩形banner/CTA，没有导航或页面框架、多个功能区域、上下文，即使精美也只是组件。完整首屏不要求展示整个滚动长页，但应有足够页面框架、导航或明确应用上下文、主体任务与功能区域；不要强制所有页面必须有顶部导航。简单登录/结算等页面可通过完整任务表单和页面上下文成立。仅点赞感谢保存作品宣传、logo品牌照片不提供页面结构。拼图或样机本身不扣分，检查里面实际页面结构和可辨信息。'
QUESTIONS={
 'structure_kind':{'type':'choice','instructions':INSTRUCTION,'criteria':{
 'full_page':'一个或多个页面展示多个有意义区域、主体任务与上下文，整体结构充分',
 'main_viewport':'完整主视口/首屏或完整任务页面，页面框架、主要任务与组件关系充分；不是孤立CTA/banner',
 'partial_page':'页面局部，能见多个关联区域但主要页面框架或任务结构缺失',
 'component':'单个孤立卡片、CTA、banner、按钮或装饰区块，缺乏页面框架和多区域任务组织',
 'promotion':'作者点赞感谢保存作品尾图、logo、纯品牌照片、色板或无界面装饰',
 'unknown':'描述不足以确定实际页面结构，保留未知'}},
 'completeness':{'type':'score','instructions':INSTRUCTION+'此分衡量作为页面训练数据的结构充分程度，不衡量好不好看。孤立组件应接近等级1，宣传图应接近0。','criteria':[
 '没有可学习的页面结构：作者宣传、点赞感谢、logo或纯照片',
 '仅单个孤立组件、banner或CTA；缺乏页面上下文和多个功能区域',
 '局部页面或数个组件，能学习部分组织关系但主要页面任务/框架不充分',
 '完整主视口或任务页面，框架、主体内容、主要操作及区域关系清楚',
 '完整丰富页面或多个完整页面，多个有意义区域、任务流程与组件关系充分清楚']}}
RULE={'version':'page-structure-v5.0','design_weights':{k:v['weight'] for k,v in DIMENSIONS.items() if k!='completeness'},'final_score':'min(design_total, completeness, structure_cap)','structure_caps':{'component':25,'promotion':0,'non_ui':0,'others':100},'high_quality':{'total_at_least':75,'completeness_at_least':70,'learnability_at_least':70,'each_design_dimension_at_least':60,'valid_ui_probability_at_least':.7},'human_calibrated':False,'purpose':'筛选页面训练数据；孤立组件和作者宣传图排在后面','preserved_design_results':'jev_results_v4.json'}

RULE.pop('high_quality')
RULE['quality_bands']={'high_quality':'total >= 65','medium_quality':'50 <= total < 65','low_quality':'total < 50'}
RULE['final_score']='min(design_total, completeness, structure_cap, each design dimension scoring below 50)'
RULE['critical_design_cap']={'dimensions':['layout','hierarchy','readability','consistency'],'trigger_below':50,'cap':'lowest triggered dimension score','purpose':'严重设计缺陷不能由完整度或可学习性抵消'}

def quality_band(total):
    return 'high_quality' if total>=65 else 'medium_quality' if total>=50 else 'low_quality'

def summarize_v5(item,answers):
    scores={**item['scores'],'completeness':answers['completeness']['score']/4*100}
    kind=answers['structure_kind']['choice']
    cap=0 if kind=='promotion' or item['page_function']=='non_ui' else 25 if kind=='component' else 100
    critical={k:scores[k] for k in ('layout','hierarchy','readability','consistency') if scores[k]<50}
    total=min(item['total'],scores['completeness'],cap,*critical.values())
    reasons=[]
    if cap==0:reasons.append('作者宣传或非界面：不属于页面训练数据，综合分为0')
    elif kind=='component':reasons.append('仅孤立组件/区块，综合分封顶25')
    for name,value in critical.items():reasons.append(f'{DIMENSIONS[name]["label"]}低于50，质量总分上限{value:.1f}')
    reasons.append('质量总分≥65：高质量' if total>=65 else '50≤质量总分<65：中质量' if total>=50 else '质量总分<50：低质量')
    return scores,total,quality_band(total),reasons

def main():
    captions=json.loads((ROOT/'captions_structured_v4.json').read_text(encoding='utf-8-sig'))
    # Human corrections come from the user's supplied images, not previous model labels.
    for caption in captions:
        if caption['sample_id']=='LP006':caption['page_structure_observation']='用户提供原图确认：仅居中青蓝色横向CTA/banner，左标题说明按钮、右抽象节点插画，周围空白背景，无导航、页面框架或其他功能区。原描述称首屏不能作为完整页面证据。'
        if caption['sample_id']=='LP030':caption['page_structure_observation']='用户提供原图确认：仅Press Like & Show some Love和保存灵感提示、点赞爱心图标，是作者作品宣传尾图，没有页面任务结构。'
    save_json(ROOT/'captions_structured_v5.json',captions)
    digest=hashlib.sha256((ROOT/'captions_structured_v5.json').read_bytes()).hexdigest()
    original={x['sample_id']:x for x in json.loads((ROOT/'jev_results_v4.json').read_text(encoding='utf-8'))}
    key=load_api_key()
    if not key:raise SystemExit('Missing API key')
    save_json(ROOT/'questions_v5.json',QUESTIONS);save_json(ROOT/'rule_v5.json',RULE)
    path=ROOT/'jev_results_v5.json';results=json.loads(path.read_text(encoding='utf-8')) if path.exists() else []
    if any(x['caption_sha256']!=digest for x in results):raise SystemExit('Caption changed since checkpoint')
    completed={x['sample_id'] for x in results}
    for caption in captions:
        sid=caption['sample_id']
        if sid in completed:continue
        state={k:v for k,v in caption.items() if k!='sample_id'}
        request=urllib.request.Request('https://api.typesafe.ai/v1/systemone',data=json.dumps({'model':'jev-latest','state':state,'questions':QUESTIONS},ensure_ascii=False).encode('utf-8'),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(request,timeout=45) as response:raw=json.load(response)
        except urllib.error.HTTPError as error:raise SystemExit(f'HTTP {error.code} on {sid}; checkpoints saved') from None
        except urllib.error.URLError:raise SystemExit(f'Network error on {sid}; checkpoints saved') from None
        answers=raw['answers']
        assert set(answers)==set(QUESTIONS) and answers['structure_kind']['choice'] in STRUCTURE_NAMES
        assert 0<=answers['completeness']['score']<=4
        base=original[sid];scores,total,quality,reasons=summarize_v5(base,answers)
        item=copy.deepcopy(base)
        item.update({'scores':scores,'design_total':base['total'],'total':total,'quality':quality,'reasons':reasons,'structure_kind':answers['structure_kind']['choice'],'structure_response':raw,'caption_sha256':digest})
        results.append(item);save_json(path,results);print(f'{sid} structure scored ({len(results)}/50)',flush=True)

if __name__=='__main__':main()

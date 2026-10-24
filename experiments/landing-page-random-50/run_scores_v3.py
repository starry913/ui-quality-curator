import json
import time
import urllib.request
import urllib.error
from run_jev import ROOT, WORKSPACE, save_json
from run_quality_experiment import QUESTIONS as V2_QUESTIONS

DIMENSIONS = {
    'layout': {'label':'布局与间距','weight':0.25,'instructions':'评价界面自身的布局、对齐、留白和分组间距。外部设备倾斜、拼图包装和未展示完整页面不自动扣分。依据具体视觉描述，不根据精美等赞美词猜测。','criteria':[
        '没有足够可辨认的界面布局，无法学习前端排版',
        '主要元素明显错位、拥挤或失衡，布局秩序差',
        '主要结构可辨认，但对齐、间距或留白存在明显不足，或描述只支持基本布局',
        '主要元素对齐合理，区块分组间距有秩序，留白和视觉平衡良好',
        '网格对齐、间距和留白处理精细一致，疏密节奏成熟且证据充分']},
    'hierarchy': {'label':'信息层级','weight':0.20,'instructions':'评价标题、正文、主视觉、操作入口之间的主次和阅读顺序。仅根据可观察证据，不因信息少或页面局部就自动判低。','criteria':[
        '没有可辨认的界面内容或没有可学习的信息层级',
        '标题正文操作入口混杂，主次严重不清',
        '能看出基本主次，但重点竞争或阅读顺序存在明显限制，或证据只支持基本层级',
        '标题正文主视觉操作入口具有清楚主次，分组合理，重点容易识别',
        '层级和阅读节奏精细成熟，重点突出而次要信息有序，具体证据充分']},
    'readability': {'label':'可读性','weight':0.15,'instructions':'评价界面主要文字及内容的字体大小、背景对比和信息密度是否便于阅读。不要把缩略预览无法逐字读小字当原图模糊。根据可观察的主要文字、密度与对比判断；无法确认的细节保留不确定性，不假造对比度数值。','criteria':[
        '没有有效界面可评价，或界面主要内容不可辨认',
        '主要标题正文大面积难辨认，字体对比或密度严重妨碍阅读',
        '主要内容基本可辨，但有明显过小字体、低对比或密集文字区域，或证据只支持基本可读性',
        '主要标题正文和操作文字可辨，字号对比及内容密度合理，少量细字或未知细节不妨碍主要阅读',
        '主要及次要内容均有充分证据支持清晰易读，字体大小对比与密度处理精细舒适']},
    'consistency': {'label':'视觉一致性','weight':0.20,'instructions':'评价字体、配色、按钮卡片图标是否构成协调的设计语言。多色块、强调字体与插画本身不等于混乱。根据具体样式协调性判断。','criteria':[
        '没有足够界面信息，无法评价前端设计语言',
        '字体颜色和可见组件明显冲突，视觉语言混乱',
        '存在基本共同风格，但组件或字体配色有明显不一致，或证据只支持基本协调',
        '字体配色和可见组件协调，强调方式有规律，主要视觉语言统一',
        '跨区块字体配色组件细节高度统一，设计语言成熟且具体证据充分']},
    'learnability': {'label':'数据可学习性','weight':0.20,'instructions':'评价图片作为前端训练数据的结构与细节价值。样机、拼图、局部区段本身不扣分。看主体UI占比、关键组件可辨程度、真实遮挡或变形。纯logo照片点赞感谢海报不算有效前端结构。','criteria':[
        '没有足够有效的前端界面，只有logo照片宣传或装饰等',
        '主体UI很小或严重变形遮挡，多数布局组件无法辨认，只能学习大致风格',
        '能学习基本布局和少量组件，但关键信息受限或界面信息较少',
        '至少一个完整区段或主要布局清楚，多数关键组件及关系可学习，允许局部小字不清',
        '布局组件与主要细节清楚，信息充分，能学习丰富成熟的页面组织或组件设计']}
}
QUESTIONS={name:{'type':'score','instructions':dimension['instructions'],'criteria':dimension['criteria']} for name,dimension in DIMENSIONS.items()}
QUESTIONS['valid_ui']=V2_QUESTIONS['valid_ui']
QUESTIONS['page_use']=V2_QUESTIONS['page_use']
RULE={'version':'scores-v3.0','score_conversion':'Jev 0-4 probability-weighted score / 4 * 100; preserve unrounded values for classification','weights':{name:dim['weight'] for name,dim in DIMENSIONS.items()},'high_quality':{'total_at_least':75,'learnability_at_least':70,'each_design_dimension_at_least':60,'valid_ui_probability_at_least':0.7,'not_non_ui':True},'human_calibrated':False}

def summarize(answers):
    scores={name:answers[name]['score']/4*100 for name in DIMENSIONS}
    total=sum(scores[name]*dim['weight'] for name,dim in DIMENSIONS.items())
    reasons=[]
    if answers['page_use']['choice']=='non_ui' or answers['valid_ui']['noul']<0.7:reasons.append('有效前端界面信息不足')
    if total<75:reasons.append('总分低于75')
    if scores['learnability']<70:reasons.append('数据可学习性低于70')
    for name in ('layout','hierarchy','readability','consistency'):
        if scores[name]<60:reasons.append(DIMENSIONS[name]['label']+'低于60')
    return scores,total,('low_quality' if reasons else 'high_quality'),reasons or ['总分及各项最低要求均达标']

def main():
    captions={x['sample_id']:x for x in json.loads((ROOT/'captions_luna.json').read_text(encoding='utf-8-sig'))}
    evidence={x['sample_id']:x for x in json.loads((ROOT/'quality_evidence_luna.json').read_text(encoding='utf-8-sig'))}
    if len(captions)!=50 or set(captions)!=set(evidence):raise SystemExit('Expected matching 50 captions and observations')
    key=next((line.split('=',1)[1].strip().strip('"').strip("'") for line in (WORKSPACE/'.env').read_text(encoding='utf-8-sig').splitlines() if line.startswith('TYPESAFE_API_KEY=')),None)
    if not key:raise SystemExit('Missing API key')
    save_json(ROOT/'score_questions_v3.json',QUESTIONS);save_json(ROOT/'score_rule_v3.json',RULE)
    path=ROOT/'jev_scores_v3.json'
    results=json.loads(path.read_text(encoding='utf-8')) if path.exists() else []
    complete={item['sample_id'] for item in results}
    for sid in sorted(captions):
        if sid in complete:continue
        state={'visual_caption':{k:v for k,v in captions[sid].items() if k!='sample_id'},'quality_observations':{k:v for k,v in evidence[sid].items() if k!='sample_id'}}
        request=urllib.request.Request('https://api.typesafe.ai/v1/systemone',data=json.dumps({'model':'jev-latest','state':state,'questions':QUESTIONS},ensure_ascii=False).encode('utf-8'),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
        start=time.monotonic()
        try:
            with urllib.request.urlopen(request,timeout=45) as response:raw=json.load(response)
        except urllib.error.HTTPError as error:raise SystemExit(f'HTTP {error.code} on {sid}; previous results saved') from None
        except urllib.error.URLError:raise SystemExit(f'Network error on {sid}; previous results saved') from None
        answers=raw.get('answers',{})
        if set(answers)!=set(QUESTIONS):raise SystemExit('Unexpected answer schema')
        for name in DIMENSIONS:
            if not 0<=answers[name]['score']<=4 or set(answers[name]['probabilities'])!={'0','1','2','3','4'}:raise SystemExit('Unexpected score scale')
        scores,total,quality,reasons=summarize(answers)
        results.append({'sample_id':sid,'quality':quality,'type':answers['page_use']['choice'],'scores':scores,'total':total,'reasons':reasons,'elapsed_seconds':round(time.monotonic()-start,3),'response':raw})
        save_json(path,results);print(f'{sid} scored ({len(results)}/50)',flush=True)

if __name__=='__main__':main()

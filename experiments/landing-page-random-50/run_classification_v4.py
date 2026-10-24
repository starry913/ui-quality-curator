import csv
import hashlib
import json
import time
import urllib.error
import urllib.request
from run_jev import ROOT, WORKSPACE, save_json, load_api_key
from run_scores_v3 import DIMENSIONS, QUESTIONS as SCORE_QUESTIONS, RULE as SCORE_RULE, summarize

FUNCTION_NAMES={'landing':'营销落地页','dashboard':'数据仪表盘','management':'业务管理页','listing':'列表/搜索页','detail':'详情页','form':'交易/表单页','content':'内容/作品集页','account':'账户/设置页','unknown':'其他/无法确定','non_ui':'非界面'}
DOMAIN_NAMES={'tourism':'旅游与酒店','finance':'金融与保险','retail':'零售与消费品','education':'教育与学习','health':'医疗与健康','real_estate':'房地产与家居','food_service':'餐饮与生活服务','professional':'企业与专业服务','technology':'科技与通用工具','media':'娱乐与媒体','public':'公共与社会服务','other':'其他领域','unknown':'无法确定','not_applicable':'不适用（非界面）'}
QUESTIONS={name:SCORE_QUESTIONS[name] for name in [*DIMENSIONS,'valid_ui']}
QUESTIONS['page_function']={'type':'choice','instructions':'判断主要界面的用户任务。整页或主要区段用于介绍推广时归营销落地页，即使内嵌dashboard、商品或手机产品图；以指标查看为主归仪表盘，以编辑记录操作为主归管理。按实际主体功能，不按来源关键词或行业猜测。多个页面时选择占主导的功能，不强猜不可见部分。','criteria':{
    'landing':'主要是产品服务品牌介绍和获客，包含首屏、介绍区段、服务预订首屏、联系方式等营销区段',
    'dashboard':'主要界面用于查看指标图表统计与状态，而不是营销页里的示意素材',
    'management':'主要用于查找修改记录、管理客户订单项目和执行操作，表格操作等占主导',
    'listing':'主要用于浏览搜索筛选多个商品酒店课程对象，实际列表为主要内容',
    'detail':'主要展示单个商品酒店课程项目的详细信息，详情阅读为主要任务',
    'form':'主要用于预订结算申请或填写提交表单，输入和交易任务占主导',
    'content':'主要用于阅读文章、浏览媒体内容或展示创作摄影个人作品集',
    'account':'主要用于登录注册、个人资料、权限或设置',
    'unknown':'确有可辨认界面，但主要用途无法判断或不属于以上功能',
    'non_ui':'缺少足够可辨认的界面，纯logo照片色板点赞感谢或作者宣传图'}}
QUESTIONS['business_domain']={'type':'choice','instructions':'根据界面里的文字、对象与服务内容判断业务领域，独立于页面功能。旅游首页与旅游后台同属旅游；金融产品营销页与金融仪表盘同属金融。不能根据配色、风格或单张装饰照片猜行业；SaaS是交付方式不是行业。未知保留未知；非界面图片归不适用。','criteria':{
    'tourism':'旅行、酒店住宿、旅游景点和旅行出行预订服务',
    'finance':'银行支付储蓄投资贷款财务与保险，服务对象是金融业务',
    'retail':'服饰美妆食品饮料数码运动用品等实体消费品的品牌和购物服务',
    'education':'学校课程教学学习培训服务',
    'health':'医疗健康治疗、心理健康、健身瑜伽与健康管理服务',
    'real_estate':'房产建筑房地产开发、室内家居设计装修家具空间服务',
    'food_service':'餐厅餐饮、清洁维修美容等线下生活服务；包装商品售卖归零售',
    'professional':'法律咨询招聘人力资源等专业企业服务',
    'technology':'开发、数据技术、协作、通用软件工具、CRM等；特定金融医疗等业务软件归其业务领域',
    'media':'音乐视频游戏摄影媒体创作与娱乐内容服务',
    'public':'政府公益社区与社会公共服务',
    'other':'能够辨认业务但不属于已列领域',
    'unknown':'界面业务线索不足或含混，不能可靠判断领域',
    'not_applicable':'不是有效前端界面，缺少可分类的界面业务领域'}}
RULE={**SCORE_RULE,'version':'classification-v4.0','classification_axes':['page_function','business_domain'],'caption_file':'captions_structured_v4.json','non_ui_domain_rule':'When page_function is non_ui, business_domain becomes not_applicable; raw model choice preserved','notes':['五项评分等级、权重与质量阈值沿用v3，caption改为结构化视觉证据。','新旧分数变化不能直接解释为准确率提升。','其他可见功能保留在caption中，本轮Jev仅输出主要功能单标签。']}

def summarize_v4(answers):
    return summarize({**answers,'page_use':answers['page_function']})

def main():
    caption_path=ROOT/'captions_structured_v4.json'
    captions_list=json.loads(caption_path.read_text(encoding='utf-8-sig'))
    captions={item['sample_id']:item for item in captions_list}
    with (ROOT/'samples.csv').open(encoding='utf-8-sig',newline='') as handle:expected={r['sample_id'] for r in csv.DictReader(handle)}
    if len(captions_list)!=50 or set(captions)!=expected:raise SystemExit('Expected matching 50 structured captions')
    required={'sample_id','content_and_purpose','layout_components','hierarchy','typography_color_components','presentation_limits','uncertainties','function_evidence','domain_evidence'}
    if any(set(item)!=required for item in captions_list):raise SystemExit('Unexpected structured caption fields')
    input_hash=hashlib.sha256(caption_path.read_bytes()).hexdigest()
    key=load_api_key()
    if not key:raise SystemExit('Missing API key')
    save_json(ROOT/'questions_v4.json',QUESTIONS);save_json(ROOT/'rule_v4.json',RULE)
    path=ROOT/'jev_results_v4.json';results=json.loads(path.read_text(encoding='utf-8')) if path.exists() else []
    if any(item.get('caption_sha256')!=input_hash for item in results):raise SystemExit('Caption changed since checkpoint; stopped to avoid mixing inputs')
    completed={item['sample_id'] for item in results}
    for sid in sorted(captions):
        if sid in completed:continue
        state={key:value for key,value in captions[sid].items() if key!='sample_id'}
        body=json.dumps({'model':'jev-latest','state':state,'questions':QUESTIONS},ensure_ascii=False).encode('utf-8')
        request=urllib.request.Request('https://api.typesafe.ai/v1/systemone',data=body,headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
        started=time.monotonic()
        try:
            with urllib.request.urlopen(request,timeout=45) as response:raw=json.load(response)
        except urllib.error.HTTPError as error:raise SystemExit(f'HTTP {error.code} on {sid}; checkpoints saved') from None
        except urllib.error.URLError:raise SystemExit(f'Network error on {sid}; checkpoints saved') from None
        answers=raw.get('answers',{})
        if set(answers)!=set(QUESTIONS):raise SystemExit('Unexpected answer schema')
        if answers['page_function']['choice'] not in FUNCTION_NAMES or answers['business_domain']['choice'] not in DOMAIN_NAMES:raise SystemExit('Unexpected category')
        for name in DIMENSIONS:
            if not 0<=answers[name]['score']<=4 or set(answers[name]['probabilities'])!={'0','1','2','3','4'}:raise SystemExit('Unexpected score scale')
        scores,total,quality,reasons=summarize_v4(answers)
        function=answers['page_function']['choice'];domain=answers['business_domain']['choice']
        normalized_domain='not_applicable' if function=='non_ui' else domain
        results.append({'sample_id':sid,'quality':quality,'page_function':function,'business_domain':normalized_domain,'raw_business_domain':domain,'scores':scores,'total':total,'reasons':reasons,'caption_sha256':input_hash,'elapsed_seconds':round(time.monotonic()-started,3),'response':raw})
        save_json(path,results);print(f'{sid} complete ({len(results)}/50)',flush=True)

if __name__=='__main__':main()

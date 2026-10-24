POLICY={'version':'decision-review-v1','boundary_margin':1,'structure_accept_probability_band':[.3,.7],'accepted_structures':['full_page','main_viewport'],'notes':'只提示可能影响保留/淘汰的边界样本；行业与功能低置信度保留在详情，不单独提示。完整页面与完整首屏属于同一可接受结构，合并概率。规则未经过人工校准。'}

def review_reasons(item,threshold=65):
    if any(item['scores'][k]<50 for k in ('layout','hierarchy','readability','consistency')):return []
    if item['structure_kind'] in ('component','promotion') or item['page_function']=='non_ui':return []
    reasons=[]
    if any(abs(item['total']-boundary)<=POLICY['boundary_margin'] for boundary in (50,65)):reasons.append('质量总分距50或65分界线不超过1分')
    p=item['structure_response']['answers']['structure_kind']['probabilities']
    accept=p['full_page']+p['main_viewport']
    if item['design_total']>=threshold and .3<=accept<=.7:reasons.append('页面结构的判断可能影响保留结果')
    return reasons

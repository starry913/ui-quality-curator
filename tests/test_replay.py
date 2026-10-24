import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
NAMES=('landing-page-random-50','dashboard-random-50')

class ReportParser(HTMLParser):
    def __init__(self):super().__init__();self.articles=0;self.metrics=0;self.images=[];self.ids=set()
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        self.articles+=tag=='article'
        self.metrics+=attrs.get('class')=='metric'
        if tag=='img':self.images.append(attrs.get('src'))
        if 'id' in attrs:self.ids.add(attrs['id'])

class OfflineReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        cls.copy=Path(cls.tmp.name)/'project'
        shutil.copytree(ROOT,cls.copy,ignore=shutil.ignore_patterns('.git','__pycache__','.env','tests'))
        env=dict(os.environ);env.pop('TYPESAFE_API_KEY',None);env['PYTHONIOENCODING']='utf-8'
        result=subprocess.run([sys.executable,str(cls.copy/'tools/replay.py')],env=env,capture_output=True,text=True,encoding='utf-8')
        if result.returncode:raise RuntimeError(result.stderr)

    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def test_all_100_scores_and_quality_bands(self):
        for name in NAMES:
            folder=self.copy/'experiments'/name
            results=json.loads((folder/'jev_results_v5.json').read_text(encoding='utf-8'))
            with (folder/'samples.csv').open(encoding='utf-8-sig',newline='') as handle:samples=list(csv.DictReader(handle))
            self.assertEqual(len(results),50)
            self.assertEqual({x['sample_id'] for x in results},{x['sample_id'] for x in samples})
            for item in results:
                scores=item['scores']
                for key in ('layout','hierarchy','readability','consistency','learnability'):
                    self.assertAlmostEqual(scores[key],item['response']['answers'][key]['score']*25)
                self.assertAlmostEqual(scores['completeness'],item['structure_response']['answers']['completeness']['score']*25)
                base=sum(scores[k]*v for k,v in {'layout':.25,'hierarchy':.2,'readability':.15,'consistency':.2,'learnability':.2}.items())
                cap=0 if item['structure_kind']=='promotion' or item['page_function']=='non_ui' else 25 if item['structure_kind']=='component' else 100
                critical=[scores[k] for k in ('layout','hierarchy','readability','consistency') if scores[k]<50]
                expected=min(base,scores['completeness'],cap,*critical)
                self.assertAlmostEqual(expected,item['total'])
                quality='high_quality' if expected>=65 else 'medium_quality' if expected>=50 else 'low_quality'
                self.assertEqual(quality,item['quality'])
            expected_counts={'high_quality':20,'medium_quality':13,'low_quality':17} if name.startswith('landing') else {'high_quality':27,'medium_quality':10,'low_quality':13}
            self.assertEqual(dict(Counter(x['quality'] for x in results)),expected_counts)

    def test_severe_readability_case(self):
        folder=self.copy/'experiments/dashboard-random-50'
        records=json.loads((folder/'jev_results_v5.json').read_text(encoding='utf-8'))
        item=next(x for x in records if x['sample_id']=='DB045')
        self.assertEqual(item['scores']['readability'],36.5)
        self.assertEqual(item['total'],36.5)
        self.assertEqual(item['quality'],'low_quality')

    def test_threshold_boundaries(self):
        folder=self.copy/'experiments/dashboard-random-50'
        command="import json; from run_structure_v5 import quality_band; print(json.dumps([quality_band(x) for x in [49.999,50,64.999,65]]))"
        result=subprocess.run([sys.executable,'-c',command],cwd=folder,capture_output=True,text=True,encoding='utf-8',check=True)
        self.assertEqual(json.loads(result.stdout),['low_quality','medium_quality','medium_quality','high_quality'])

    def test_report_works_without_redistributed_images(self):
        for name in NAMES:
            folder=self.copy/'experiments'/name
            page=(folder/'review.html').read_text(encoding='utf-8');parser=ReportParser();parser.feed(page)
            self.assertEqual(parser.articles,50)
            self.assertEqual(parser.metrics,300)
            self.assertEqual(parser.images,[])
            self.assertTrue({'quality','function','domain','sort','direction','medium','download'}<=parser.ids)
            self.assertIn('查看来源作品',page)
            self.assertNotIn('E:/',page)
            self.assertNotIn('设计总分',page)
            with (folder/'classification_scores_v5.csv').open(encoding='utf-8-sig',newline='') as handle:export=list(csv.DictReader(handle))
            self.assertEqual(len(export),50)
            self.assertNotIn('design_total',export[0])

if __name__=='__main__':unittest.main()

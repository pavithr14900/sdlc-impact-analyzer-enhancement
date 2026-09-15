import { createRoot } from 'react-dom/client';
import ChangeImpactResults, { type ImpactResult } from './src/ChangeImpactResults';
import './src/App.css';
import fixture from './report-check.json';
const data = fixture as ImpactResult;
const mode = new URLSearchParams(location.search).get('mode');
if (mode === 'old' && data.report) { delete data.report.behavior_changes; delete data.report.contract_impacts; }
if (mode === 'legacy') { data.report = null; data.document = '## Change summary\n\nApply a discount.\n\n## Tests to run\n\nVerify checkout totals.'; }
if (mode === 'empty' && data.report) { data.report.affected_components = []; data.report.dependencies = []; data.report.risks = []; data.report.actions = []; data.report.tests = []; data.findings = { evidence: [], warnings: [] }; }
document.body.style.cssText = 'margin:0;background:#f4f6fb;font-family:Segoe UI,sans-serif;';
createRoot(document.getElementById('root')!).render(<main style={{maxWidth:1100,margin:'0 auto',padding:20}}><ChangeImpactResults result={data.document} data={data} /></main>);

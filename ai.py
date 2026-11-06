"""Optional AI explanation. Sends no student ID, grades, full transcript or private records.
The AI never changes plans; the planner remains authoritative for modeled constraints.
"""
import os,json,urllib.request,urllib.error

def evidence(report,strategy):
    item=report['plans'][strategy]
    if not item['ok']:raise ValueError('Cannot explain a blocked plan')
    p=item['plan'];v=p['verification'];st=report['student']
    return {
      'program_id':report['program_id'],'strategy':strategy,
      'student_interest_ratings':st.get('preferences',{}).get('interest_weights',{}),
      'career_interests':st.get('preferences',{}).get('career_tags',[]),
      'terms':[{'term':x['term'],'credits':x['credits'],
                'items':[{'id':i['id'],'title':i['title'],'credits':i['credits'], 'kind':i['kind']} for i in x['items']]}
               for x in p['terms']],
      'selected_requirement_choices':p['group_choices'],
      'validation':{'modeled_pass':v['modeled_pass'],'manual_checks':v['manual_review'],
                    'course_availability_verified':v['campus_offerings_verified'],
                    'provisional_slots':v['provisional_slots']},
      'note':'Provisional modeled pathway. Do not claim official degree audit, advisor approval or confirmed offerings.'
    }

def explain_with_openai(report,strategy,question,model=None):
    key=os.environ.get('OPENAI_API_KEY','').strip()
    if not key:raise RuntimeError('OPENAI_API_KEY not configured. Offline explanation is still available.')
    if not question.strip():raise ValueError('Please enter a question')
    model=model or os.environ.get('OPENAI_MODEL','gpt-4.1-mini')
    payload={'model':model,'temperature':0.2,'max_tokens':380,
        'messages':[{'role':'system','content':('You are an academic decision-support explainer. Only use the supplied evidence. '
         'Never invent course eligibility, prerequisite fulfillment, real course availability, graduation dates, approvals, or official guarantees. '
         'Explain trade-offs and mention relevant manual checks. Do not modify the proposed plan.')},
         {'role':'user','content':'QUESTION: '+question.strip()[:500]+'\nEVIDENCE: '+json.dumps(evidence(report,strategy),ensure_ascii=False)}]}
    req=urllib.request.Request('https://api.openai.com/v1/chat/completions',
       data=json.dumps(payload).encode('utf-8'),headers={'Authorization':'Bearer '+key,
       'Content-Type':'application/json'},method='POST')
    try:
        with urllib.request.urlopen(req,timeout=25) as response:
            body=json.loads(response.read())
        return body['choices'][0]['message']['content']
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f'AI API HTTP error {exc.code}. Check API key, model and billing.') from exc
    except Exception as exc:
        raise RuntimeError('AI explanation failed; local planning remains available: '+str(exc)) from exc

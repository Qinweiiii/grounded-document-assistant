DOCS = {'policy': 'Employees receive 20 days of paid leave.', 'support': 'Support hours are 9am to 5pm.'}
def retrieve(query):
    terms = set(query.lower().split())
    return sorted(DOCS.items(), key=lambda d: len(terms & set(d[1].lower().split())), reverse=True)
if __name__ == '__main__':
    for q in ['paid leave', 'support hours', 'office location']:
        print(q, retrieve(q)[0])

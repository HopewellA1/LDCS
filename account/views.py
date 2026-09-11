from django.shortcuts import render




def signup(request):
    
    return render(request, 'account/signup.html')



def login(request):
    
    return render(request, 'account/login.html')

#@login_required
def changePassword(request):
    
    
    return render(request, 'account/changePassword.html')

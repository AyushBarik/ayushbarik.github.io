document.addEventListener('DOMContentLoaded', function() {
    const emailLink = document.getElementById('emailUnscrambleLink');
    const emailDisplayText = document.getElementById('emailDisplayText');
  
    if (emailLink && emailDisplayText) {
      const userPart = emailLink.getAttribute('data-user');
      const domainPart = emailLink.getAttribute('data-domain');
      const realEmail = userPart + '@' + domainPart;
      
      const initialScrambledEmailHTML = "rba2ki@linoisli.ued<br>(click to unscramble)";
      const initialScrambledEmailPart = "rba2ki@linoisli.ued"; 
      
      emailDisplayText.innerHTML = initialScrambledEmailHTML;
  
      let isUnscrambling = false;
  
      emailLink.addEventListener('click', function(event) {
        event.preventDefault();
  
        if (isUnscrambling || emailDisplayText.textContent.startsWith(realEmail)) { 
          return;
        }
        isUnscrambling = true;
  
        let currentIndex = 0;
        let currentDisplayArray = initialScrambledEmailPart.split('');
        const realEmailArray = realEmail.split('');
        
        let intervalTime = 100; 
  
        const unscrambleInterval = setInterval(function() {
          for (let i = 0; i <= currentIndex; i++) {
            if (i < realEmailArray.length) {
              currentDisplayArray[i] = realEmailArray[i];
            }
          }
          
          let displayTextDuringAnimation = currentDisplayArray.join('');
          
          if (currentIndex < realEmail.length -1) {
               displayTextDuringAnimation += "<br>(click to unscramble)";
               emailDisplayText.innerHTML = displayTextDuringAnimation;
          } else {
              emailDisplayText.textContent = realEmail;
          }
  
          currentIndex++;
  
          if (currentIndex >= realEmail.length) {
            clearInterval(unscrambleInterval);
            emailDisplayText.textContent = realEmail;
            emailLink.setAttribute('href', 'mailto:' + realEmail);
            isUnscrambling = false;
          }
        }, intervalTime);
      });
    }
  });
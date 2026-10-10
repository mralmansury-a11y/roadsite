/* إدارة خدمات الطريق الدولي — سلوكيات الواجهة (بدون مكتبات) */
(function () {
  'use strict';

  /* 1) قائمة الجوال: فتح/إغلاق، الإغلاق بالنقر خارجها أو بمفتاح Esc أو عند اختيار رابط */
  var btn = document.querySelector('.burger');
  var nav = document.getElementById('nv');
  if (btn && nav) {
    var setOpen = function (open, focusBtn) {
      nav.classList.toggle('open', open);
      btn.setAttribute('aria-expanded', String(open));
      btn.setAttribute('aria-label', open ? 'إغلاق القائمة' : 'فتح القائمة');
      if (!open && focusBtn) btn.focus();
    };
    btn.addEventListener('click', function () {
      var open = btn.getAttribute('aria-expanded') !== 'true';
      setOpen(open);
      if (open) { var first = nav.querySelector('a'); if (first) first.focus(); }
    });
    document.addEventListener('click', function (e) {
      if (nav.classList.contains('open') && !nav.contains(e.target) && !btn.contains(e.target)) setOpen(false);
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && nav.classList.contains('open')) setOpen(false, true);
    });
    nav.addEventListener('click', function (e) { if (e.target.closest('a')) setOpen(false); });
    // إغلاق القائمة تلقائيًا عند التحول إلى عرض سطح المكتب
    var mq = window.matchMedia('(min-width:1024px)');
    var onMq = function () { if (mq.matches) setOpen(false); };
    mq.addEventListener ? mq.addEventListener('change', onMq) : mq.addListener(onMq);
  }

  /* 2) زر إغلاق تنبيهات flash */
  document.addEventListener('click', function (e) {
    var x = e.target.closest('.flash-x');
    if (x) x.closest('.flash').remove();
  });

  /* 3) التحقق من نموذج التواصل قبل الإرسال (يطابق شروط الخادم: الاسم + الرسالة + هاتف أو بريد) */
  var form = document.querySelector('form[data-contact]');
  if (form) {
    var $ = function (id) { return document.getElementById(id); };
    var show = function (input, msgId, bad) {
      var field = input.closest('.field'), msg = $(msgId);
      field.classList.toggle('invalid', bad);
      input.setAttribute('aria-invalid', String(bad));
      if (msg) { msg.hidden = !bad; bad ? input.setAttribute('aria-describedby', msgId) : input.removeAttribute('aria-describedby'); }
      return bad;
    };
    var check = function () {
      var name = $('f-name'), body = $('f-body'), email = $('f-email'), phone = $('f-phone');
      var reachBad = !phone.value.trim() && !email.value.trim();
      var emailBad = email.value.trim() !== '' && !email.validity.valid;
      var errs = [
        show(name, 'e-name', !name.value.trim()) && name,
        show(email, 'e-reach', reachBad || emailBad) && email,
        show(body, 'e-body', !body.value.trim()) && body
      ].filter(Boolean);
      if (reachBad) phone.closest('.field').classList.add('invalid'); else phone.closest('.field').classList.remove('invalid');
      return errs;
    };
    form.addEventListener('submit', function (e) {
      var errs = check();
      if (errs.length) { e.preventDefault(); errs[0].focus(); }
      else { var b = form.querySelector('[type=submit]'); b.disabled = true; b.setAttribute('aria-busy', 'true'); }
    });
    // إعادة تفعيل الزر عند الرجوع للصفحة من ذاكرة المتصفح
    window.addEventListener('pageshow', function () { var b = form.querySelector('[type=submit]'); b.disabled = false; b.removeAttribute('aria-busy'); });
    // إعادة التحقق أثناء الكتابة بعد أول محاولة إرسال فاشلة
    form.addEventListener('input', function () { if (form.querySelector('.invalid')) check(); });
  }
})();

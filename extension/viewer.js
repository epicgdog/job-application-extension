(async()=>{
  const $=id=>document.getElementById(id);
  const call=async(op,id)=>{const result=await chrome.runtime.sendMessage({type:'applyflow',op,id});if(!result?.ok)throw new Error(result?.error||'Background unavailable.');return result.data;};
  try{
    const id=new URL(location.href).searchParams.get('id');
    if(!/^[0-9a-f-]{36}$/.test(id||''))throw new Error('Invalid resume link.');
    const [row,pdf]=await Promise.all([call('get',id),call('pdf',id)]);
    const bytes=Uint8Array.from(atob(pdf.base64),c=>c.charCodeAt(0));
    const url=URL.createObjectURL(new Blob([bytes],{type:'application/pdf'}));
    $('title').textContent=row.job.company+' · '+row.job.title;
    $('status').textContent='One page verified. Original bullet text preserved. Review before attaching it to your application.';
    $('pdf').src=url;$('pdf').hidden=false;$('download').disabled=false;
    $('download').onclick=()=>{
      const a=document.createElement('a');a.href=url;
      a.download=(row.job.company+'-'+row.job.title).replace(/[^a-z0-9-]+/gi,'-').slice(0,120)+'-resume.pdf';a.click();
    };
    window.addEventListener('unload',()=>URL.revokeObjectURL(url));
  }catch(error){$('status').textContent=error.message;}
})();

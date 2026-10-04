const JOBS=[
{id:1,title:"Network Engineer",dept:"Technology",location:"Port Moresby",apps:127,workflow:"Fully Automated",threshold:75,screened:127,passed:34,shortlisted:18,interviews:7,status:"Open"},
{id:2,title:"Systems Analyst",dept:"Technology",location:"Port Moresby",apps:86,workflow:"Semi-Automated",threshold:70,screened:42,passed:17,shortlisted:9,interviews:4,status:"Open"},
{id:3,title:"Cybersecurity Analyst",dept:"Information Security",location:"Port Moresby",apps:64,workflow:"Fully Automated",threshold:80,screened:64,passed:21,shortlisted:12,interviews:3,status:"Open"},
{id:4,title:"Software Engineer",dept:"Digital",location:"Hybrid",apps:91,workflow:"Semi-Automated",threshold:75,screened:0,passed:0,shortlisted:0,interviews:0,status:"Open"}
];
const APPLICATIONS=[
{id:101,candidate:"Maria Kila",email:"maria@example.com",jobId:1,status:"Screening",score:91,result:"Passed",submitted:"29 Sep 2026",workflow:"Fully Automated"},
{id:102,candidate:"John Peter",email:"john@example.com",jobId:1,status:"Shortlisted",score:88,result:"Passed",submitted:"29 Sep 2026",workflow:"Fully Automated"},
{id:103,candidate:"Sarah Wali",email:"sarah@example.com",jobId:1,status:"Screening",score:72,result:"Failed",submitted:"28 Sep 2026",workflow:"Fully Automated"},
{id:104,candidate:"David Toma",email:"david@example.com",jobId:2,status:"Submitted",score:null,result:"Waiting",submitted:"29 Sep 2026",workflow:"Semi-Automated"},
{id:105,candidate:"James Nalo",email:"james@example.com",jobId:2,status:"Shortlisted",score:84,result:"Passed",submitted:"28 Sep 2026",workflow:"Semi-Automated"},
{id:106,candidate:"Peter Leo",email:"peter@example.com",jobId:3,status:"Rejected",score:48,result:"Failed",submitted:"27 Sep 2026",workflow:"Fully Automated"}
];
function params(){return new URLSearchParams(location.search)}
function jobById(id){return JOBS.find(j=>j.id==id)||JOBS[0]}
function appById(id){return APPLICATIONS.find(a=>a.id==id)||APPLICATIONS[0]}
function jobUrl(id){return `job.html?id=${id}`}
function applicationUrl(id){return `application.html?id=${id}`}
const JOB_CRITERIA={1:[{id:'technical',name:'Technical Skills',weight:35,requirements:[{id:'python',name:'Python',required:true},{id:'django',name:'Django',required:true},{id:'sql',name:'SQL',required:true},{id:'security',name:'Security knowledge',required:false}]},{id:'experience',name:'Experience',weight:30,requirements:[{id:'years',name:'Relevant experience',required:true},{id:'enterprise',name:'Enterprise systems',required:false},{id:'support',name:'Application support',required:false}]},{id:'education',name:'Education',weight:20,requirements:[{id:'degree',name:'IT / Computer Science degree',required:true},{id:'cert',name:'Relevant certification',required:false}]},{id:'behavioral',name:'Behavioral & Other',weight:15,requirements:[{id:'communication',name:'Communication',required:false},{id:'leadership',name:'Leadership',required:false}]}]};

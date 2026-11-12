import {defineConfig,devices} from '@playwright/test';

export default defineConfig({
  testDir:'./tests', fullyParallel:false, timeout:30000,
  use:{baseURL:process.env.E2E_BASE_URL||'http://127.0.0.1:3080',trace:'retain-on-failure',screenshot:'only-on-failure',channel:'chrome'},
  reporter:[['list'],['html',{open:'never'}]],
  projects:[{name:'desktop',use:{viewport:{width:1440,height:1000}}},{name:'mobile',use:{...devices['Pixel 7'],channel:'chrome'}}]
});

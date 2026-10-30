<template>
  <el-container style="height: 100vh; margin: 0">
    <el-aside width="200px" style="background: #304156; height: 100vh; overflow-y: auto">
      <div style="color: #fff; padding: 20px; font-weight: bold">LLM Eval</div>
      <el-menu router background-color="#304156" text-color="#bfcbd9" active-text-color="#409EFF" style="border-right: none">
        <el-menu-item index="/dashboard">监控看板</el-menu-item>
        <el-menu-item index="/prompts">Prompt 版本</el-menu-item>
        <el-menu-item index="/datasets">评测集</el-menu-item>
        <el-menu-item index="/runs">评测记录</el-menu-item>
      </el-menu>
    </el-aside>
    <el-main style="padding: 20px">
      <router-view />
    </el-main>
  </el-container>
</template>

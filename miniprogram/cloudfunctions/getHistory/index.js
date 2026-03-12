// 云函数入口文件
const cloud = require('wx-server-sdk')

cloud.init({ env: cloud.DYNAMIC_CURRENT_ENV })

const db = cloud.database()

// 云函数入口函数
exports.main = async (event, context) => {
  const { openid, username } = event
  
  try {
    // 支持通过 openid 或 username 查询
    const query = openid ? { openid: openid } : { username: username }
    
    const result = await db.collection('evaluations')
      .where(query)
      .orderBy('timestamp', 'desc')
      .limit(50)
      .get()

    return {
      data: result.data
    }
  } catch (err) {
    console.error(err)
    return {
      data: [],
      error: err.message
    }
  }
}
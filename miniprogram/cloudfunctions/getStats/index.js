// 云函数入口文件
const cloud = require('wx-server-sdk')

cloud.init({ env: cloud.DYNAMIC_CURRENT_ENV })

const db = cloud.database()
const _ = db.command

// 云函数入口函数
exports.main = async (event, context) => {
  const { openid } = event
  
  try {
    // 获取总数
    const countResult = await db.collection('evaluations')
      .where({
        openid: openid
      })
      .count()

    // 获取所有记录计算平均分和最高分
    const recordsResult = await db.collection('evaluations')
      .where({
        openid: openid
      })
      .field({
        totalScore: true
      })
      .get()

    const records = recordsResult.data
    let avgScore = 0
    let highestScore = 0

    if (records.length > 0) {
      const sum = records.reduce((acc, cur) => acc + (cur.totalScore || 0), 0)
      avgScore = Math.round(sum / records.length)
      highestScore = Math.max(...records.map(r => r.totalScore || 0))
    }

    return {
      totalCount: countResult.total,
      avgScore: avgScore,
      highestScore: highestScore
    }
  } catch (err) {
    console.error(err)
    return {
      totalCount: 0,
      avgScore: 0,
      highestScore: 0,
      error: err.message
    }
  }
}
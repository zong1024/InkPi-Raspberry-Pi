// 云函数入口文件 - 上传评测结果（供树莓派调用）
const cloud = require('wx-server-sdk')

cloud.init({ env: cloud.DYNAMIC_CURRENT_ENV })

const db = cloud.database()

// 云函数入口函数
exports.main = async (event, context) => {
  const {
    openid,           // 用户openid
    title,            // 标题
    totalScore,       // 总分
    detailScores,     // 四维评分 { structure, stroke, balance, rhythm }
    feedback,         // 评价反馈
    imageUrl,         // 原图URL（云存储）
    processedImageUrl,// 处理后图片URL
    recognizedChar,   // 识别的汉字
    confidence        // 识别置信度
  } = event

  try {
    const result = await db.collection('evaluations').add({
      data: {
        openid: openid,
        title: title || '书法评测',
        totalScore: totalScore || 0,
        detailScores: detailScores || {
          structure: 0,
          stroke: 0,
          balance: 0,
          rhythm: 0
        },
        feedback: feedback || '',
        imageUrl: imageUrl || '',
        processedImageUrl: processedImageUrl || '',
        recognizedChar: recognizedChar || '',
        confidence: confidence || 0,
        timestamp: Date.now()
      }
    })

    return {
      success: true,
      id: result._id,
      message: '上传成功'
    }
  } catch (err) {
    console.error(err)
    return {
      success: false,
      error: err.message
    }
  }
}
// 云函数入口文件
const cloud = require('wx-server-sdk')

cloud.init({ env: cloud.DYNAMIC_CURRENT_ENV })

const db = cloud.database()
const usersCollection = db.collection('users')

// 云函数入口函数
exports.main = async (event, context) => {
  const { username, password } = event
  const wxContext = cloud.getWXContext()

  // 如果没有传用户名密码，返回微信openid登录
  if (!username || !password) {
    return {
      openid: wxContext.OPENID,
      appid: wxContext.APPID,
      unionid: wxContext.UNIONID
    }
  }

  try {
    // 查询用户
    const userResult = await usersCollection
      .where({ username: username })
      .get()

    if (userResult.data.length > 0) {
      // 用户存在，验证密码
      const user = userResult.data[0]
      
      if (user.password === password) {
        // 登录成功
        return {
          success: true,
          isNewUser: false,
          openid: wxContext.OPENID,
          userInfo: {
            _id: user._id,
            username: user.username,
            nickName: user.nickName || user.username,
            createdAt: user.createdAt
          }
        }
      } else {
        // 密码错误
        return {
          success: false,
          message: '密码错误'
        }
      }
    } else {
      // 用户不存在，自动注册
      const newUser = {
        username: username,
        password: password,
        nickName: username,
        openid: wxContext.OPENID,
        createdAt: Date.now()
      }

      const createResult = await usersCollection.add({ data: newUser })

      return {
        success: true,
        isNewUser: true,
        openid: wxContext.OPENID,
        userInfo: {
          _id: createResult._id,
          username: username,
          nickName: username,
          createdAt: newUser.createdAt
        }
      }
    }
  } catch (err) {
    console.error('登录失败', err)
    return {
      success: false,
      message: '服务器错误，请重试'
    }
  }
}
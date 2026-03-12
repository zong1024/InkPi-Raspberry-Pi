// pages/detail/detail.js
const app = getApp();

Page({
  data: {
    loading: true,
    id: '',
    detail: {
      totalScore: 0,
      detailScores: {
        structure: 0,
        stroke: 0,
        balance: 0,
        rhythm: 0
      },
      feedback: '',
      imageUrl: '',
      recognizedChar: '',
      confidence: 0
    }
  },

  onLoad: function (options) {
    const id = options.id;
    this.setData({ id });
    this.loadDetail(id);
  },

  onReady: function () {
    // 页面渲染完成后绘制雷达图
  },

  // 加载详情
  loadDetail: async function (id) {
    this.setData({ loading: true });

    try {
      const res = await wx.cloud.callFunction({
        name: 'getDetail',
        data: { id }
      });

      if (res.result.data) {
        this.setData({
          loading: false,
          detail: res.result.data
        });
        
        // 绘制雷达图
        this.drawRadarChart(res.result.data.detailScores);
      }
    } catch (err) {
      console.error('获取详情失败', err);
      
      // 模拟数据
      const mockDetail = {
        totalScore: 84,
        detailScores: {
          structure: 83,
          stroke: 78,
          balance: 91,
          rhythm: 84
        },
        feedback: '太棒了！您的书法水平很高，请继续保持！结构匀称，笔画流畅，整体平衡性较好。建议继续加强笔画的起收笔训练，使笔画更加有力。',
        imageUrl: '/images/sample1.png',
        recognizedChar: '永',
        confidence: 95
      };

      this.setData({
        loading: false,
        detail: mockDetail
      });

      this.drawRadarChart(mockDetail.detailScores);
    }
  },

  // 绘制雷达图
  drawRadarChart: function (scores) {
    const query = wx.createSelectorQuery();
    query.select('#radarCanvas')
      .fields({ node: true, size: true })
      .exec((res) => {
        if (!res[0]) return;

        const canvas = res[0].node;
        const ctx = canvas.getContext('2d');
        
        const dpr = wx.getSystemInfoSync().pixelRatio;
        const width = res[0].width;
        const height = res[0].height;
        
        canvas.width = width * dpr;
        canvas.height = height * dpr;
        ctx.scale(dpr, dpr);

        const centerX = width / 2;
        const centerY = height / 2;
        const radius = Math.min(width, height) / 2 - 40;

        // 绘制背景网格
        this.drawRadarGrid(ctx, centerX, centerY, radius);
        
        // 绘制数据
        this.drawRadarData(ctx, centerX, centerY, radius, scores);
      });
  },

  // 绘制雷达图网格
  drawRadarGrid: function (ctx, cx, cy, r) {
    const levels = 4;
    const labels = ['结构', '笔画', '平衡', '韵律'];
    const angleStep = (Math.PI * 2) / 4;

    // 绘制同心圆
    for (let i = 1; i <= levels; i++) {
      ctx.beginPath();
      ctx.strokeStyle = '#e0e0e0';
      ctx.lineWidth = 1;
      
      for (let j = 0; j <= 4; j++) {
        const angle = j * angleStep - Math.PI / 2;
        const x = cx + (r * i / levels) * Math.cos(angle);
        const y = cy + (r * i / levels) * Math.sin(angle);
        
        if (j === 0) {
          ctx.moveTo(x, y);
        } else {
          ctx.lineTo(x, y);
        }
      }
      ctx.closePath();
      ctx.stroke();
    }

    // 绘制轴线和标签
    ctx.font = '14px sans-serif';
    ctx.fillStyle = '#666';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';

    for (let i = 0; i < 4; i++) {
      const angle = i * angleStep - Math.PI / 2;
      const x = cx + r * Math.cos(angle);
      const y = cy + r * Math.sin(angle);
      
      ctx.beginPath();
      ctx.strokeStyle = '#e0e0e0';
      ctx.moveTo(cx, cy);
      ctx.lineTo(x, y);
      ctx.stroke();

      // 标签位置
      const labelX = cx + (r + 25) * Math.cos(angle);
      const labelY = cy + (r + 25) * Math.sin(angle);
      ctx.fillText(labels[i], labelX, labelY);
    }
  },

  // 绘制雷达图数据
  drawRadarData: function (ctx, cx, cy, r, scores) {
    const values = [
      scores.structure,
      scores.stroke,
      scores.balance,
      scores.rhythm
    ];
    const angleStep = (Math.PI * 2) / 4;

    ctx.beginPath();
    ctx.fillStyle = 'rgba(224, 50, 41, 0.3)';
    ctx.strokeStyle = '#e03229';
    ctx.lineWidth = 2;

    for (let i = 0; i < 4; i++) {
      const angle = i * angleStep - Math.PI / 2;
      const value = values[i] / 100;
      const x = cx + r * value * Math.cos(angle);
      const y = cy + r * value * Math.sin(angle);
      
      if (i === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    }

    ctx.closePath();
    ctx.fill();
    ctx.stroke();

    // 绘制数据点
    ctx.fillStyle = '#e03229';
    for (let i = 0; i < 4; i++) {
      const angle = i * angleStep - Math.PI / 2;
      const value = values[i] / 100;
      const x = cx + r * value * Math.cos(angle);
      const y = cy + r * value * Math.sin(angle);
      
      ctx.beginPath();
      ctx.arc(x, y, 4, 0, Math.PI * 2);
      ctx.fill();
    }
  },

  // 返回
  onBack: function () {
    wx.navigateBack();
  }
});
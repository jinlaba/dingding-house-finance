import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# 设置页面配置
st.set_page_config(
    page_title="顶鼎房屋财务数据分析平台",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 定义颜色主题
colors = {
    'primary': '#2E86AB',
    'secondary': '#A23B72',
    'success': '#43AA8B',
    'danger': '#F24236',
    'warning': '#FCBF49',
    'info': '#3F88C5',
    'light': '#F8F9FA',
    'dark': '#212529'
}

# ---------------------- 数据加载模块 ----------------------
@st.cache_data
def load_data():
    """加载和预处理数据，完整保留所有原始字段"""
    # 加载完整费用数据，保留所有列
    expense_df = pd.read_csv('房源月度费用汇总表_清理后.csv')
    
    # 数据类型标准化
    expense_df['年份'] = expense_df['年份'].astype(int)
    expense_df['月份'] = expense_df['月份'].astype(int)
    expense_df['日期'] = pd.to_datetime(expense_df['年份'].astype(str) + '-' + expense_df['月份'].astype(str) + '-01')
    
    # 预处理空值
    expense_df = expense_df.fillna('')
    
    return expense_df

# 加载数据
expense_df = load_data()

# 预定义字段分类（适配透视表）
filter_fields = ['组织', '店面', '年份', '月份']
row_fields = ['物业地址楼栋单元门牌号房间号', '金蝶房源类型', '最早托管开始时间', '最晚托管到期时间', '组织', '店面']
column_fields = ['大类', '年份', '月份', '组织', '店面']
value_fields = ['金额']
agg_funcs = {
    '求和': 'sum',
    '平均值': 'mean',
    '计数': 'count',
    '最大值': 'max',
    '最小值': 'min'
}

# ---------------------- 页面标题和导航 ----------------------
st.title("🏠 顶鼎房屋财务数据分析平台")
st.markdown("---")

# 侧边栏导航
sidebar_option = st.sidebar.selectbox(
    "选择分析模块",
    [
        "📊 数据概览",
        "📈 经营业绩分析",
        "💸 费用结构分析",
        "🏢 物业项目分析",
        "📋 透视表与数据导出"
    ]
)

# ---------------------- 数据概览模块（已修复+调整） ----------------------
if sidebar_option == "📊 数据概览":
    st.header("数据概览")
    st.markdown("### 核心指标卡片")
    
    # 获取最新月份数据
    latest_year = expense_df['年份'].max()
    latest_month = expense_df[expense_df['年份'] == latest_year]['月份'].max()
    latest_data = expense_df[(expense_df['年份'] == latest_year) & (expense_df['月份'] == latest_month)]
    
    # 计算核心指标（修复abs报错，总利润改为净收入）
    total_income = latest_data[latest_data['金额'] > 0]['金额'].sum() / 10000
    total_expense = abs(latest_data[latest_data['金额'] < 0]['金额'].sum()) / 10000  # 修复abs报错
    net_income = total_income - total_expense  # 净收入=总收入-总支出，原总利润逻辑
    
    # 核心指标卡片
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label=f"{latest_year}年{latest_month}月总收入（万元）",
            value=f"{total_income:.2f}"
        )
    
    with col2:
        st.metric(
            label=f"{latest_year}年{latest_month}月总支出（万元）",
            value=f"{total_expense:.2f}"
        )
    
    with col3:
        st.metric(
            label=f"{latest_year}年{latest_month}月净收入（万元）",
            value=f"{net_income:.2f}",
            delta_color="normal" if net_income > 0 else "inverse"
        )
    
    with col4:
        st.metric(
            label="数据总记录数",
            value=f"{len(expense_df):,}"
        )
    
    st.markdown("---")
    
    # 组织+大类透视汇总表
    st.subheader("组织-大类金额透视汇总（万元）")
    pivot_org_category = pd.pivot_table(
        expense_df,
        index=['组织'],
        columns=['大类'],
        values='金额',
        aggfunc='sum',
        fill_value=0
    ) / 10000  # 转换为万元
    st.dataframe(pivot_org_category.style.format("{:.2f}"), use_container_width=True)
    
    st.markdown("---")
    
    # 数据基本信息
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("数据范围")
        st.write(f"📅 时间范围：{expense_df['年份'].min()} - {expense_df['年份'].max()}年")
        st.write(f"🏢 物业项目数：{expense_df['物业地址楼栋单元门牌号房间号'].nunique()}个")
        st.write(f"🏬 组织数量：{expense_df['组织'].nunique()}个")
        st.write(f"🏪 门店数量：{expense_df['店面'].nunique()}个")
        st.write(f"🏠 房源类型数：{expense_df['金蝶房源类型'].nunique()}类")
        st.write(f"💼 费用大类数：{expense_df['大类'].nunique()}类")
    
    with col2:
        st.subheader("全量数据收入结构TOP5")
        income_by_category = expense_df[expense_df['金额'] > 0].groupby('大类')['金额'].sum().sort_values(ascending=False).head(5) / 10000
        for category, amount in income_by_category.items():
            st.write(f"{category}：{amount:.2f}万元")
    
    st.markdown("---")
    
    # 数据预览
    st.subheader("原始数据预览")
    st.dataframe(expense_df.head(20), use_container_width=True, hide_index=True)

# ---------------------- 经营业绩分析模块（已修复+新增房源类型对比） ----------------------
elif sidebar_option == "📈 经营业绩分析":
    st.header("经营业绩分析")
    
    # 时间筛选器 - 默认选择最晚年份和月份
    latest_year = expense_df['年份'].max()
    latest_month = expense_df[expense_df['年份'] == latest_year]['月份'].max()
    
    col1, col2 = st.columns(2)
    with col1:
        selected_year = st.selectbox("选择年份", sorted(expense_df['年份'].unique(), reverse=True), index=0)
    with col2:
        available_months = sorted(expense_df[expense_df['年份']==selected_year]['月份'].unique(), reverse=True)
        selected_month = st.selectbox("选择月份", available_months, index=0)
    
    # 筛选数据
    filtered_data = expense_df[(expense_df['年份'] == selected_year) & (expense_df['月份'] == selected_month)]
    
    # 计算业绩指标 - 按大类净额（修复abs报错）
    category_net = filtered_data.groupby('大类')['金额'].sum().reset_index()
    category_net['金额（万元）'] = category_net['金额'] / 10000
    category_net['类型'] = category_net['金额'].apply(lambda x: '收入' if x > 0 else '支出')
    
    total_income = category_net[category_net['金额'] > 0]['金额'].sum() / 10000
    total_expense = abs(category_net[category_net['金额'] < 0]['金额'].sum()) / 10000  # 修复abs报错
    net_income = total_income - total_expense  # 净收入=总收入-总支出
    expense_income_ratio = (total_expense/total_income*100) if total_income>0 else 0
    
    # 业绩指标卡片
    st.markdown("### 月度业绩指标")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("总收入（万元）", f"{total_income:.2f}")
    
    with col2:
        st.metric("总支出（万元）", f"{total_expense:.2f}")
    
    with col3:
        st.metric("净收入（万元）", f"{net_income:.2f}", 
                  delta_color="normal" if net_income > 0 else "inverse")
    
    with col4:
        st.metric("支出收入比", f"{expense_income_ratio:.2f}%")
    
    st.markdown("---")
    
    # 收入支出结构分析
    col1, col2 = st.columns(2)
    
    with col1:
        # 收入结构
        income_data = category_net[category_net['金额'] > 0].sort_values('金额', ascending=False)
        if len(income_data) > 0:
            fig1 = px.pie(
                values=income_data['金额（万元）'],
                names=income_data['大类'],
                title=f"{selected_year}年{selected_month}月收入结构",
                color_discrete_sequence=px.colors.qualitative.Set3
            )
            st.plotly_chart(fig1, use_container_width=True)
        else:
            st.info("本月暂无收入数据")
    
    with col2:
        # 支出结构
        expense_data = category_net[category_net['金额'] < 0].copy()
        expense_data['金额（万元）'] = expense_data['金额（万元）'].abs()
        expense_data = expense_data.sort_values('金额', ascending=False)
        if len(expense_data) > 0:
            fig2 = px.pie(
                values=expense_data['金额（万元）'],
                names=expense_data['大类'],
                title=f"{selected_year}年{selected_month}月支出结构",
                color_discrete_sequence=px.colors.qualitative.Set2
            )
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("本月暂无支出数据")
    
    st.markdown("---")
    
    # 大类净额对比
    st.subheader("大类净额对比")
    if len(category_net) > 0:
        fig3 = px.bar(
            category_net,
            x='大类',
            y='金额（万元）',
            color='类型',
            title=f"{selected_year}年{selected_month}月各大类净额",
            color_discrete_map={'收入': colors['success'], '支出': colors['danger']}
        )
        st.plotly_chart(fig3, use_container_width=True)
        
        # 大类净额明细
        st.subheader("大类净额明细")
        st.dataframe(
            category_net[['大类', '类型', '金额（万元）']].sort_values('金额（万元）', key=abs, ascending=False),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("本月暂无数据")
    
    st.markdown("---")
    
    # 新增：房源类型净收入对比
    st.subheader("🏠 房源类型净收入对比")
    # 按房源类型分组计算
    house_type_data = filtered_data.groupby('金蝶房源类型').agg(
        总收入=('金额', lambda x: x[x>0].sum()/10000),
        总支出=('金额', lambda x: abs(x[x<0].sum())/10000),
        净收入=('金额', lambda x: (x[x>0].sum() + x[x<0].sum())/10000)
    ).reset_index()
    # 过滤掉空类型
    house_type_data = house_type_data[house_type_data['金蝶房源类型'] != '']
    
    if len(house_type_data) > 0:
        # 净收入对比图表
        fig4 = px.bar(
            house_type_data.sort_values('净收入', ascending=False),
            x='金蝶房源类型',
            y='净收入',
            title=f"{selected_year}年{selected_month}月各房源类型净收入对比（万元）",
            color='净收入',
            color_continuous_scale=[colors['danger'], colors['light'], colors['success']],
            labels={'金蝶房源类型': '房源类型', '净收入': '净收入（万元）'}
        )
        fig4.update_layout(coloraxis_showscale=False)
        st.plotly_chart(fig4, use_container_width=True)
        
        # 房源类型明细表格
        st.dataframe(
            house_type_data.sort_values('净收入', ascending=False).style.format("{:.2f}", subset=['总收入', '总支出', '净收入']),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("本月暂无房源类型数据")

# ---------------------- 费用结构分析模块 ----------------------
elif sidebar_option == "💸 费用结构分析":
    st.header("费用结构分析")
    
    # 筛选控件
    col1, col2, col3 = st.columns(3)
    with col1:
        year_options = sorted(expense_df['年份'].unique(), reverse=True)
        year_filter = st.selectbox("年份筛选", year_options, index=0)
    with col2:
        category_options = ['全部'] + sorted(expense_df['大类'].unique())
        category_filter = st.selectbox("费用大类筛选", category_options, index=0)
    with col3:
        org_options = ['全部'] + sorted(expense_df['组织'].unique())
        org_filter = st.selectbox("组织筛选", org_options, index=0)
    
    # 筛选数据
    filtered_data = expense_df[expense_df['年份'] == year_filter]
    if category_filter != '全部':
        filtered_data = filtered_data[filtered_data['大类'] == category_filter]
    if org_filter != '全部':
        filtered_data = filtered_data[filtered_data['组织'] == org_filter]
    
    st.markdown("### 费用分布分析")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # 月度费用趋势
        monthly_expense = filtered_data.groupby('月份')['金额'].sum().reset_index()
        monthly_expense['金额（万元）'] = monthly_expense['金额'] / 10000
        
        fig1 = px.line(
            monthly_expense,
            x='月份',
            y='金额（万元）',
            title=f"{year_filter}年月度费用趋势",
            markers=True,
            color_discrete_sequence=[colors['primary']]
        )
        fig1.update_xaxes(tickvals=list(range(1, 13)))
        st.plotly_chart(fig1, use_container_width=True)
    
    with col2:
        # 费用大类分布
        category_expense = filtered_data.groupby('大类')['金额'].sum().sort_values(ascending=False) / 10000
        
        fig2 = px.bar(
            x=category_expense.index,
            y=category_expense.values,
            title=f"{year_filter}年费用大类分布",
            labels={'x': '费用大类', 'y': '金额（万元）'},
            orientation='v',
            color=category_expense.values,
            color_continuous_scale=[colors['danger'], colors['light'], colors['success']]
        )
        fig2.update_layout(coloraxis_showscale=False)
        st.plotly_chart(fig2, use_container_width=True)
    
    st.markdown("---")
    
    # 费用明细数据
    st.subheader("费用明细数据")
    if len(filtered_data) > 0:
        st.dataframe(
            filtered_data[['物业地址楼栋单元门牌号房间号', '组织', '店面', '大类', '月份', '金额']].sort_values('金额', key=abs, ascending=False),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("暂无符合条件的数据")

# ---------------------- 物业项目分析模块 ----------------------
elif sidebar_option == "🏢 物业项目分析":
    st.header("物业项目分析")
    
    # 筛选控件
    col1, col2, col3 = st.columns(3)
    with col1:
        # 只显示前100个项目，避免下拉框过长
        project_options = ['全部'] + sorted(expense_df['物业地址楼栋单元门牌号房间号'].unique())[:100]
        project_filter = st.selectbox("选择物业项目", project_options, index=0)
    with col2:
        year_options = sorted(expense_df['年份'].unique(), reverse=True)
        year_filter = st.selectbox("年份", year_options, index=0)
    with col3:
        category_options = ['全部'] + sorted(expense_df['大类'].unique())
        category_filter = st.selectbox("费用类型", category_options, index=0)
    
    # 筛选数据
    filtered_data = expense_df[expense_df['年份'] == year_filter]
    if project_filter != '全部':
        filtered_data = filtered_data[filtered_data['物业地址楼栋单元门牌号房间号'] == project_filter]
    if category_filter != '全部':
        filtered_data = filtered_data[filtered_data['大类'] == category_filter]
    
    # 物业项目概况
    st.markdown("### 物业项目概况")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_projects = expense_df['物业地址楼栋单元门牌号房间号'].nunique()
        st.metric("总物业项目数", total_projects)
    
    with col2:
        active_projects = filtered_data['物业地址楼栋单元门牌号房间号'].nunique()
        st.metric(f"{year_filter}年活跃项目数", active_projects)
    
    with col3:
        total_income = filtered_data[filtered_data['金额'] > 0]['金额'].sum() / 10000
        st.metric(f"{year_filter}年总收入（万元）", f"{total_income:.2f}")
    
    with col4:
        avg_income = total_income / active_projects if active_projects > 0 else 0
        st.metric("项目平均收入（万元）", f"{avg_income:.2f}")
    
    st.markdown("---")
    
    # 项目业绩分析
    st.subheader("项目业绩排名")
    
    # 项目收入排名
    if len(filtered_data) > 0:
        project_income = filtered_data[filtered_data['金额'] > 0].groupby('物业地址楼栋单元门牌号房间号')['金额'].sum().sort_values(ascending=False).head(10) / 10000
        
        if len(project_income) > 0:
            fig1 = px.bar(
                x=project_income.index,
                y=project_income.values,
                title=f"{year_filter}年物业项目收入TOP10",
                labels={'x': '物业项目', 'y': '收入（万元）'},
                color=project_income.values,
                color_continuous_scale=px.colors.sequential.Greens
            )
            fig1.update_layout(xaxis_tickangle=-45)
            st.plotly_chart(fig1, use_container_width=True)
        else:
            st.info("暂无收入数据")
        
        # 项目费用排名
        project_expense = filtered_data[filtered_data['金额'] < 0].groupby('物业地址楼栋单元门牌号房间号')['金额'].sum().abs().sort_values(ascending=False).head(10) / 10000
        
        if len(project_expense) > 0:
            fig2 = px.bar(
                x=project_expense.index,
                y=project_expense.values,
                title=f"{year_filter}年物业项目支出TOP10",
                labels={'x': '物业项目', 'y': '支出（万元）'},
                color=project_expense.values,
                color_continuous_scale=px.colors.sequential.Reds
            )
            fig2.update_layout(xaxis_tickangle=-45)
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("暂无支出数据")
    
    # 项目数据表格
    st.markdown("### 项目详细数据")
    if len(filtered_data) > 0:
        st.dataframe(
            filtered_data[['物业地址楼栋单元门牌号房间号', '组织', '店面', '大类', '月份', '金额']].sort_values('金额', key=abs, ascending=False),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("暂无数据")

# ---------------------- 透视表与数据导出模块 ----------------------
elif sidebar_option == "📋 透视表与数据导出":
    st.header("交互式透视表与数据导出")
    st.markdown("完全复刻Excel透视表操作模式，支持自定义筛选、行、列、值配置")
    
    # 分区域配置
    st.markdown("### 🔍 筛选器配置")
    filter_col1, filter_col2, filter_col3, filter_col4 = st.columns(4)
    
    with filter_col1:
        selected_org = st.multiselect("组织", options=sorted(expense_df['组织'].unique()), default=[])
    with filter_col2:
        selected_shop = st.multiselect("店面", options=sorted(expense_df['店面'].unique()), default=[])
    with filter_col3:
        selected_year = st.multiselect("年份", options=sorted(expense_df['年份'].unique()), default=[])
    with filter_col4:
        selected_month = st.multiselect("月份", options=sorted(expense_df['月份'].unique()), default=[])
    
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 📋 行字段配置")
        selected_rows = st.multiselect(
            "选择要放在行的字段",
            options=row_fields,
            default=['物业地址楼栋单元门牌号房间号', '金蝶房源类型']
        )
    with col2:
        st.markdown("### 📊 列字段配置")
        selected_columns = st.multiselect(
            "选择要放在列的字段",
            options=column_fields,
            default=['大类']
        )
    
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 📈 值字段配置")
        selected_value = st.selectbox("选择值字段", options=value_fields, index=0)
    with col2:
        st.markdown("### 🔢 聚合方式")
        selected_agg = st.selectbox("选择聚合函数", options=list(agg_funcs.keys()), index=0)
    
    # 筛选数据
    pivot_data = expense_df.copy()
    if selected_org:
        pivot_data = pivot_data[pivot_data['组织'].isin(selected_org)]
    if selected_shop:
        pivot_data = pivot_data[pivot_data['店面'].isin(selected_shop)]
    if selected_year:
        pivot_data = pivot_data[pivot_data['年份'].isin(selected_year)]
    if selected_month:
        pivot_data = pivot_data[pivot_data['月份'].isin(selected_month)]
    
    # 生成透视表
    st.markdown("---")
    st.subheader("📋 透视表结果")
    
    if len(pivot_data) == 0:
        st.warning("暂无符合筛选条件的数据，请调整筛选条件")
    else:
        if not selected_rows and not selected_columns:
            st.warning("请至少选择一个行字段或列字段")
        else:
            # 动态生成透视表
            try:
                pivot_table = pd.pivot_table(
                    pivot_data,
                    index=selected_rows if selected_rows else None,
                    columns=selected_columns if selected_columns else None,
                    values=selected_value,
                    aggfunc=agg_funcs[selected_agg],
                    fill_value=0,
                    margins=True,
                    margins_name='合计'
                )
                
                # 格式化金额为2位小数
                pivot_table = pivot_table.round(2)
                
                # 展示透视表
                st.dataframe(pivot_table, use_container_width=True)
                
                # 数据导出
                st.markdown("---")
                col1, col2, col3 = st.columns(3)
                with col2:
                    csv_data = pivot_table.to_csv(encoding='utf-8-sig')
                    st.download_button(
                        label="📥 下载透视表数据",
                        data=csv_data,
                        file_name="顶鼎房屋_财务透视表.csv",
                        mime='text/csv',
                        type="primary"
                    )
                
                # 原始数据导出
                st.markdown("---")
                st.subheader("📦 原始筛选数据导出")
                st.dataframe(pivot_data.head(20), use_container_width=True, hide_index=True)
                
                raw_csv = pivot_data.to_csv(index=False, encoding='utf-8-sig')
                st.download_button(
                    label="📥 下载完整原始筛选数据",
                    data=raw_csv,
                    file_name="顶鼎房屋_筛选后原始数据.csv",
                    mime='text/csv'
                )
                
            except Exception as e:
                st.error(f"生成透视表失败：{str(e)}，请调整字段配置")

# ---------------------- 页脚 ----------------------
st.markdown("---")
st.markdown(
    """
    <div style="text-align: center; color: #666; font-size: 14px;">
        <p>顶鼎房屋财务数据分析平台 | 数据更新时间：2026年2月</p>
        <p>© 2026 顶鼎房屋 版权所有</p>
    </div>
    """,
    unsafe_allow_html=True
)

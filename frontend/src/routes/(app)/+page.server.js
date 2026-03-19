import { apiRequest } from '$lib/api-helpers.js';

/** @type {import('./$types').PageServerLoad} */
export async function load({ locals, cookies }) {
  const userId = locals.user?.id;
  const org = locals.org;

  if (!userId || !org) {
    return {
      error: 'User not authenticated'
    };
  }

  try {
    // Fetch dashboard data from Django API
    const dashboardResponse = await apiRequest('/dashboard/', {}, { cookies, org });
    
    if (!dashboardResponse || typeof dashboardResponse !== 'object') {
      throw new Error('Invalid dashboard response structure');
    }

    // transform tasks from dashboard response
    const upcomingTasks = (dashboardResponse.tasks || [])
      .filter((task) => {
        const isAssignedToUser = task.assigned_to && task.assigned_to.some((p) => 
          p.user_details && p.user_details.id === userId
        );
        const isNotCompleted = task.status !== 'Completed';
        return isAssignedToUser && isNotCompleted;
      })
      .slice(0, 5)
      .map((task) => ({
        id: task.id,
        subject: task.title,
        status: task.status,
        priority: task.priority,
        dueDate: task.due_date
      }));

    return {
      metrics: {
        totalLeads: dashboardResponse.leads_count || 0,
        totalOpportunities: dashboardResponse.opportunities_count || 0,
        totalAccounts: dashboardResponse.accounts_count || 0,
        totalContacts: dashboardResponse.contacts_count || 0,
        pendingTasks: upcomingTasks.length,
        opportunityRevenue: (dashboardResponse.opportunities || []).reduce(
          (sum, opp) => sum + (opp.amount ? parseFloat(opp.amount) : 0),
          0
        )
      },
      recentData: {
        leads: (dashboardResponse.leads || []).slice(0, 5).map(l => ({
          id: l.id,
          firstName: l.first_name,
          lastName: l.last_name,
          company: l.company_name || null,
          status: l.status,
          createdAt: l.created_at
        })),
        opportunities: (dashboardResponse.opportunities || []).slice(0, 5).map(o => ({
          id: o.id,
          name: o.name,
          amount: o.amount ? parseFloat(o.amount) : null,
          currency: o.currency || null,
          stage: o.stage,
          probability: o.probability ? parseFloat(o.probability) : null,
          createdAt: o.created_at,
          closed_on: o.closed_on,
          account: o.account ? { name: o.account.name } : null
        })),
        tasks: upcomingTasks,
        activities: (dashboardResponse.activities || []).map((activity) => ({
          id: activity.id,
          user: {
            name: activity.user?.name || activity.user?.email?.split('@')[0] || 'Unknown'
          },
          action: activity.action,
          entityType: activity.entity_type,
          entityId: activity.entity_id,
          entityName: activity.entity_name,
          description:
            activity.description ||
            `${activity.action_display || ''} ${activity.entity_type || ''}: ${activity.entity_name || ''}`,
          timestamp: activity.timestamp,
          humanizedTime: activity.humanized_time
        }))
      },
      urgentCounts: dashboardResponse.urgent_counts || {
        overdue_tasks: 0,
        tasks_due_today: 0,
        followups_today: 0,
        hot_leads: 0
      },
      pipelineByStage: dashboardResponse.pipeline_by_stage || {},
      revenueMetrics: dashboardResponse.revenue_metrics || {
        pipeline_value: 0,
        weighted_pipeline: 0,
        won_this_month: 0,
        conversion_rate: 0
      },
      hotLeads: (dashboardResponse.hot_leads || []).map((lead) => ({
        id: lead.id,
        first_name: lead.first_name,
        last_name: lead.last_name,
        company: lead.company || lead.company_name,
        rating: lead.rating,
        next_follow_up: lead.next_follow_up,
        last_contacted: lead.last_contacted
      })),
      goalSummary: dashboardResponse.goal_summary || []
    };
  } catch (error) {
    console.error('DASHBOARD_FATAL_ERROR:', error);
    return {
      error: 'Failed to load dashboard data: ' + error.message
    };
  }
}

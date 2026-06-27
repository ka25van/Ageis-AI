import { LayoutDashboard, GitBranch, Database, Bot, Activity, Server } from 'lucide-react'

const stats = [
  { name: 'Projects', value: '12', icon: GitBranch, color: 'text-blue-600 bg-blue-100' },
  { name: 'Repositories', value: '48', icon: Database, color: 'text-green-600 bg-green-100' },
  { name: 'Agents', value: '7', icon: Bot, color: 'text-purple-600 bg-purple-100' },
  { name: 'Active Runs', value: '3', icon: Activity, color: 'text-orange-600 bg-orange-100' },
]

const recentActivity = [
  { id: 1, action: 'Repository indexed', target: 'github.com/user/repo', time: '2 min ago', status: 'completed' },
  { id: 2, action: 'Agent run completed', target: 'Code Review Agent', time: '15 min ago', status: 'completed' },
  { id: 3, action: 'Documentation generated', target: 'API docs', time: '1 hour ago', status: 'completed' },
  { id: 4, action: 'Incident analysis', target: 'Production outage', time: '3 hours ago', status: 'in_progress' },
]

export function Dashboard() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Dashboard</h1>
        <p className="mt-1 text-gray-500">Overview of your Aegis AI workspace</p>
      </div>

      {/* Stats Grid */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat) => (
          <div key={stat.name} className="rounded-lg border border-gray-200 bg-white p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-500">{stat.name}</p>
                <p className="mt-1 text-3xl font-bold text-gray-900">{stat.value}</p>
              </div>
              <div className={cn('p-3 rounded-lg', stat.color)}>
                <stat.icon className="h-6 w-6" aria-hidden="true" />
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Quick Actions */}
      <div className="rounded-lg border border-gray-200 bg-white">
        <div className="border-b border-gray-200 px-6 py-4">
          <h2 className="text-lg font-semibold text-gray-900">Quick Actions</h2>
        </div>
        <div className="grid gap-4 p-6 sm:grid-cols-2 lg:grid-cols-4">
          <button className="group flex flex-col items-center gap-3 rounded-lg border border-gray-200 p-6 hover:border-blue-300 hover:bg-blue-50 transition-colors">
            <div className="p-3 rounded-lg bg-blue-100 text-blue-600 group-hover:bg-blue-200">
              <LayoutDashboard className="h-6 w-6" />
            </div>
            <span className="text-sm font-medium text-gray-700">New Project</span>
          </button>
          <button className="group flex flex-col items-center gap-3 rounded-lg border border-gray-200 p-6 hover:border-blue-300 hover:bg-blue-50 transition-colors">
            <div className="p-3 rounded-lg bg-green-100 text-green-600 group-hover:bg-green-200">
              <GitBranch className="h-6 w-6" />
            </div>
            <span className="text-sm font-medium text-gray-700">Connect Repository</span>
          </button>
          <button className="group flex flex-col items-center gap-3 rounded-lg border border-gray-200 p-6 hover:border-blue-300 hover:bg-blue-50 transition-colors">
            <div className="p-3 rounded-lg bg-purple-100 text-purple-600 group-hover:bg-purple-200">
              <Bot className="h-6 w-6" />
            </div>
            <span className="text-sm font-medium text-gray-700">Run Agent</span>
          </button>
          <button className="group flex flex-col items-center gap-3 rounded-lg border border-gray-200 p-6 hover:border-blue-300 hover:bg-blue-50 transition-colors">
            <div className="p-3 rounded-lg bg-orange-100 text-orange-600 group-hover:bg-orange-200">
              <Server className="h-6 w-6" />
            </div>
            <span className="text-sm font-medium text-gray-700">Deploy</span>
          </button>
        </div>
      </div>

      {/* Recent Activity */}
      <div className="rounded-lg border border-gray-200 bg-white">
        <div className="border-b border-gray-200 px-6 py-4">
          <h2 className="text-lg font-semibold text-gray-900">Recent Activity</h2>
        </div>
        <div className="divide-y divide-gray-200">
          {recentActivity.map((activity) => (
            <div key={activity.id} className="px-6 py-4 hover:bg-gray-50">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div className={cn(
                    'p-2 rounded-lg',
                    activity.status === 'completed' ? 'bg-green-100 text-green-600' :
                    activity.status === 'in_progress' ? 'bg-blue-100 text-blue-600' :
                    'bg-gray-100 text-gray-600'
                  )}>
                    <Activity className="h-4 w-4" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-gray-900">{activity.action}</p>
                    <p className="text-sm text-gray-500">{activity.target}</p>
                  </div>
                </div>
                <span className="text-sm text-gray-400">{activity.time}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function cn(...inputs: (string | boolean | undefined)[]) {
  return inputs.filter(Boolean).join(' ')
}
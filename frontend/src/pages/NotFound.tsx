import { Link } from 'react-router'
import { EmptyState } from '../components/ui'

export default function NotFound() {
  return (
    <EmptyState title="Page not found" action={<Link to="/" className="text-accent hover:underline">Back to Mission Overview</Link>}>
      This address does not match any LunarLab view.
    </EmptyState>
  )
}

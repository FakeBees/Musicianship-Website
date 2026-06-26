"""
curriculum.py — helper functions for the module/curriculum system.
"""
from models import db, Module, ModuleExercise, ClassModuleExercise, ModuleCompletion


def effective_exercises(class_obj, module):
    """
    Return the effective list of exercises for `module` in `class_obj`,
    applying ClassModuleExercise overrides.

    Returns a list of dicts:
      {
        'source': 'course' | 'class',
        'module_exercise_id': int | None,
        'class_exercise_id': int | None,
        'exercise_type': str,
        'exercise_id': int,
        'order': int,
        'completion_criterion': dict,
      }
    """
    removed_ids = set()
    overrides   = {}  # module_exercise_id -> ClassModuleExercise
    additions   = []

    for cme in ClassModuleExercise.query.filter_by(class_id=class_obj.id).all():
        if cme.action == 'remove' and cme.module_exercise_id:
            removed_ids.add(cme.module_exercise_id)
        elif cme.action == 'override' and cme.module_exercise_id:
            overrides[cme.module_exercise_id] = cme
        elif cme.action == 'add' and cme.module_id == module.id:
            additions.append(cme)

    result = []
    for me in module.exercises.order_by(ModuleExercise.order).all():
        if me.id in removed_ids:
            continue
        if me.id in overrides:
            cme = overrides[me.id]
            result.append({
                'source': 'class',
                'module_exercise_id': me.id,
                'class_exercise_id': cme.id,
                'exercise_type': cme.exercise_type or me.exercise_type,
                'exercise_id': cme.exercise_id or me.exercise_id,
                'order': cme.order if cme.order is not None else me.order,
                'completion_criterion': cme.completion_criterion or me.completion_criterion,
            })
        else:
            result.append({
                'source': 'course',
                'module_exercise_id': me.id,
                'class_exercise_id': None,
                'exercise_type': me.exercise_type,
                'exercise_id': me.exercise_id,
                'order': me.order,
                'completion_criterion': me.completion_criterion,
            })

    for cme in additions:
        result.append({
            'source': 'class',
            'module_exercise_id': None,
            'class_exercise_id': cme.id,
            'exercise_type': cme.exercise_type,
            'exercise_id': cme.exercise_id,
            'order': cme.order or 9999,
            'completion_criterion': cme.completion_criterion or {'attempts': 1},
        })

    result.sort(key=lambda x: x['order'])
    return result


def get_completion(user_id, class_id, module_exercise_id=None, class_exercise_id=None):
    """Return ModuleCompletion or None."""
    q = ModuleCompletion.query.filter_by(user_id=user_id, class_id=class_id)
    if module_exercise_id is not None:
        q = q.filter_by(module_exercise_id=module_exercise_id)
    if class_exercise_id is not None:
        q = q.filter_by(class_exercise_id=class_exercise_id)
    return q.first()


def mark_complete(user_id, class_id, module_exercise_id=None, class_exercise_id=None, score=None):
    """
    Mark a module exercise complete for the student. Idempotent — updates best_score if higher.
    """
    existing = get_completion(user_id, class_id, module_exercise_id, class_exercise_id)
    if existing:
        if score is not None and (existing.best_score is None or score > existing.best_score):
            existing.best_score = score
            db.session.commit()
        return existing

    mc = ModuleCompletion(
        user_id=user_id,
        class_id=class_id,
        module_exercise_id=module_exercise_id,
        class_exercise_id=class_exercise_id,
        best_score=score,
    )
    db.session.add(mc)
    db.session.commit()
    return mc


def completion_map(user_id, class_id):
    """
    Return a set of (module_exercise_id, class_exercise_id) tuples that are completed
    for this user in this class.
    """
    completions = ModuleCompletion.query.filter_by(user_id=user_id, class_id=class_id).all()
    return {(c.module_exercise_id, c.class_exercise_id) for c in completions}


def next_incomplete(user_id, class_id, class_obj, module):
    """
    Return the first exercise dict (from effective_exercises) in `module` that is not
    yet completed for this user in this class. Returns None if all are done.
    """
    done = completion_map(user_id, class_id)
    for ex in effective_exercises(class_obj, module):
        key = (ex['module_exercise_id'], ex['class_exercise_id'])
        if key not in done:
            return ex
    return None


def modules_with_progress(user_id, class_id, class_obj):
    """
    For each module in the class's course, return:
      {'module': Module, 'total': int, 'completed': int, 'exercises': list}
    Returns [] if class has no course.
    """
    if not class_obj.course_id:
        return []
    result = []
    done = completion_map(user_id, class_id)
    for module in class_obj.course.modules.order_by(Module.order).all():
        exs = effective_exercises(class_obj, module)
        completed_count = sum(
            1 for ex in exs
            if (ex['module_exercise_id'], ex['class_exercise_id']) in done
        )
        result.append({
            'module': module,
            'total': len(exs),
            'completed': completed_count,
            'exercises': exs,
        })
    return result
